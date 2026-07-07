from typing import Callable

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

PADDING = 14
TAIL = 10
CORNER_R = 12
MAX_TEXT_WIDTH = 240
CLOSE_BTN_SIZE = 22
GROW_MS = 550          # blow-out animation duration
START_BUBBLE_W = 44    # size of the "still coming out of the mouth" bubble
START_BUBBLE_H = 32
# Warmer, attention-grabbing palette — feels like a real reminder note.
BG_COLOR = QColor(255, 249, 236, 245)
BORDER_COLOR = QColor(210, 155, 60, 140)
TEXT_COLOR = QColor(50, 40, 20)
SHAKE_FRAMES = ((6, 0), (-6, 0), (5, 0), (-5, 0), (3, 0), (-3, 0), (0, 0))
SHAKE_INTERVAL_MS = 55


class SpeechBubble(QWidget):
    """Frameless, translucent bubble that gets "blown out" from the pet's mouth.
    Grows from a tiny circle near the mouth up to full size at the pet's head level.
    Emits `closed` whenever the bubble is hidden — so callers can restore state."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._text = ""
        self._tail_on_left = True
        self._font = QFont("PingFang SC", 13)
        self._target = None  # PetWindow — kept loose to avoid an import cycle
        self._reply_callback: Callable[[str], None] | None = None
        self._base_pos = QPoint(0, 0)
        self._final_size = (0, 0)
        self._shake_idx = 0
        self._growing = False
        self._grow_anim: QPropertyAnimation | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._shake_timer = QTimer(self)
        self._shake_timer.setInterval(SHAKE_INTERVAL_MS)
        self._shake_timer.timeout.connect(self._advance_shake)

        self._close_btn = QPushButton("×", self)
        self._close_btn.setFixedSize(CLOSE_BTN_SIZE, CLOSE_BTN_SIZE)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent;"
            " color: rgba(90, 60, 30, 200); font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { color: #c0392b; }"
        )
        self._close_btn.clicked.connect(self.hide)
        self._close_btn.hide()  # only reveal after growth completes

    # ---------- public API ----------

    def blow_out_from(self, pet, text: str, duration_ms: int = 0) -> None:
        """Animate the bubble growing out of `pet`'s mouth and landing at head level.
        `pet` must expose `head_point()` and `mouth_point()` returning global QPoints."""
        self._text = text
        self._target = pet
        final_rect, tail_left = self._compute_final_rect(pet)
        self._tail_on_left = tail_left
        self._final_size = (final_rect.width(), final_rect.height())
        self._base_pos = QPoint(final_rect.x(), final_rect.y())

        # Start rect: tiny bubble centered at the mouth.
        mouth = pet.mouth_point()
        start_rect = QRect(
            mouth.x() - START_BUBBLE_W // 2,
            mouth.y() - START_BUBBLE_H // 2,
            START_BUBBLE_W,
            START_BUBBLE_H,
        )

        self.setGeometry(start_rect)
        self._position_close_button()
        self._close_btn.hide()
        self.show()
        self.raise_()

        if self._grow_anim is not None:
            self._grow_anim.stop()
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(GROW_MS)
        anim.setStartValue(start_rect)
        anim.setEndValue(final_rect)
        anim.setEasingCurve(QEasingCurve.OutBack)
        self._grow_anim = anim
        self._growing = True
        anim.start()
        # QPropertyAnimation.finished can be flaky under some QPA plugins;
        # a QTimer is a reliable belt-and-braces trigger.
        QTimer.singleShot(GROW_MS + 40, self._on_grow_finished)

        self._hide_timer.stop()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms + GROW_MS)

    def reposition(self) -> None:
        """Called when the pet moves. Snap to the new head position instantly."""
        if self._target is None or not self.isVisible() or self._growing:
            return
        final_rect, tail_left = self._compute_final_rect(self._target)
        if tail_left != self._tail_on_left:
            self._tail_on_left = tail_left
            self.update()
        self._base_pos = QPoint(final_rect.x(), final_rect.y())
        self.setGeometry(final_rect)
        self._position_close_button()

    def set_reply_callback(self, cb: Callable[[str], None] | None) -> None:
        self._reply_callback = cb

    # ---------- layout helpers ----------

    def _compute_final_rect(self, pet) -> tuple[QRect, bool]:
        fm = QFontMetrics(self._font)
        text_rect = fm.boundingRect(
            QRect(0, 0, MAX_TEXT_WIDTH, 400),
            int(Qt.TextWordWrap),
            self._text,
        )
        body_w = max(140, text_rect.width() + 2 * PADDING + CLOSE_BTN_SIZE)
        body_h = max(56, text_rect.height() + 2 * PADDING)
        total_w = body_w + TAIL
        total_h = body_h

        screen = QApplication.primaryScreen().availableGeometry()
        pet_geom = pet.frameGeometry()
        right_x = pet_geom.right() + 6
        left_x = pet_geom.left() - total_w - 6
        if right_x + total_w <= screen.right():
            x = right_x
            tail_left = True
        elif left_x >= screen.left():
            x = left_x
            tail_left = False
        else:
            x = max(screen.left(), min(right_x, screen.right() - total_w))
            tail_left = True

        head = pet.head_point()
        y = head.y() - total_h // 2
        y = max(screen.top(), min(y, screen.bottom() - total_h))
        return QRect(x, y, total_w, total_h), tail_left

    def _position_close_button(self) -> None:
        body_right = self.width() - (TAIL if not self._tail_on_left else 0)
        self._close_btn.move(body_right - CLOSE_BTN_SIZE - 4, 4)

    # ---------- animation callbacks ----------

    def _on_grow_finished(self) -> None:
        if not self._growing:
            return  # idempotent — animation already reset us
        self._growing = False
        w, h = self._final_size
        if w and h:
            self.setGeometry(self._base_pos.x(), self._base_pos.y(), w, h)
        self._position_close_button()
        self._close_btn.show()
        self.update()  # transition from blob-only paint to text+tail paint
        self._start_shake()

    def _start_shake(self) -> None:
        self._shake_idx = 0
        self._shake_timer.start()

    def _advance_shake(self) -> None:
        if self._shake_idx >= len(SHAKE_FRAMES):
            self._shake_timer.stop()
            self.move(self._base_pos)
            return
        dx, dy = SHAKE_FRAMES[self._shake_idx]
        self._shake_idx += 1
        self.move(self._base_pos.x() + dx, self._base_pos.y() + dy)

    # ---------- Qt events ----------

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._hide_timer.stop()
        self._shake_timer.stop()
        if self._grow_anim is not None:
            self._grow_anim.stop()
        self._growing = False
        self.closed.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_close_button()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._tail_on_left:
            body = QRectF(TAIL, 0, self.width() - TAIL, self.height())
        else:
            body = QRectF(0, 0, self.width() - TAIL, self.height())
        # During growth: only draw a smooth rounded blob, no tail, no text.
        if self._growing:
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), CORNER_R, CORNER_R)
            p.setBrush(BG_COLOR)
            p.setPen(QPen(BORDER_COLOR, 1))
            p.drawPath(path)
            return

        path = QPainterPath()
        path.addRoundedRect(body, CORNER_R, CORNER_R)
        tail_y = self.height() / 2
        tail = QPainterPath()
        if self._tail_on_left:
            tail.moveTo(body.left(), tail_y - TAIL)
            tail.lineTo(0, tail_y)
            tail.lineTo(body.left(), tail_y + TAIL)
        else:
            tail.moveTo(body.right(), tail_y - TAIL)
            tail.lineTo(self.width(), tail_y)
            tail.lineTo(body.right(), tail_y + TAIL)
        tail.closeSubpath()
        path.addPath(tail)

        p.setBrush(BG_COLOR)
        p.setPen(QPen(BORDER_COLOR, 1))
        p.drawPath(path)

        p.setPen(TEXT_COLOR)
        p.setFont(self._font)
        right_pad = PADDING + CLOSE_BTN_SIZE
        text_rect = body.adjusted(PADDING, PADDING, -right_pad, -PADDING)
        p.drawText(
            text_rect,
            int(Qt.TextWordWrap | Qt.AlignVCenter | Qt.AlignLeft),
            self._text,
        )
        if self._reply_callback is not None:
            hint = QFont("PingFang SC", 10)
            p.setFont(hint)
            p.setPen(QColor(120, 120, 120))
            p.drawText(
                body.adjusted(0, 0, -6, -2),
                int(Qt.AlignRight | Qt.AlignBottom),
                "点我回复 💬",
            )

    def mousePressEvent(self, event) -> None:
        if self._growing:
            return
        if event.button() == Qt.LeftButton and self._reply_callback is not None:
            text = self._text
            self.hide()
            self._reply_callback(text)
            return
        if event.button() == Qt.RightButton:
            self.hide()
