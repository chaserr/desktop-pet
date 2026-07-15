"""Amber reminder speech bubble. Rounded rect body + tail pointing at the pet,
text + × close button, small attention shake on show. No grow animation, no
sparkles — just the final popup."""
from typing import Callable

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

# ---------- geometry / typography ----------
PADDING = 14
TAIL = 10
CORNER_R = 12
MAX_TEXT_WIDTH = 240
CLOSE_BTN_SIZE = 22
FINAL_FONT_PT = 13

# ---------- palette ----------
BG_COLOR = QColor(255, 249, 236, 245)
BORDER_COLOR = QColor(210, 155, 60, 140)
TEXT_COLOR = QColor(50, 40, 20)

# ---------- attention shake ----------
SHAKE_FRAMES = ((6, 0), (-6, 0), (5, 0), (-5, 0), (3, 0), (-3, 0), (0, 0))
SHAKE_INTERVAL_MS = 55


class SpeechBubble(QWidget):
    """Amber rounded-rect reminder bubble with a tail poking at the pet. Text
    is left-aligned; a × close button sits in the top-right; when a reply
    callback is set, clicking the body forwards the text to it."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
            | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._text = ""
        self._font = QFont("PingFang SC", FINAL_FONT_PT)
        self._target = None
        self._reply_callback: Callable[[str], None] | None = None
        self._tail_on_left = True
        self._final_rect = QRect()
        self._base_pos = QPoint(0, 0)
        self._state = "idle"  # idle | shown
        self._shake_idx = 0

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._shake_timer = QTimer(self)
        self._shake_timer.setInterval(SHAKE_INTERVAL_MS)
        self._shake_timer.timeout.connect(self._advance_shake)

        self._close_btn = QPushButton("×", self)
        self._close_btn.setFixedSize(CLOSE_BTN_SIZE, CLOSE_BTN_SIZE)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFocusPolicy(Qt.NoFocus)
        self._close_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent;"
            " color: rgba(90, 60, 30, 200); font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { color: #c0392b; }"
        )
        self._close_btn.clicked.connect(self.hide)
        self._close_btn.hide()

    # ---------- public API ----------

    def blow_out_from(self, pet, text: str, duration_ms: int = 0) -> None:
        """Show the amber bubble beside `pet` with `text`. Optional auto-hide
        after `duration_ms` (0 = keep until the user clicks ×)."""
        self._text = text
        self._target = pet

        rect, tail_left = self._compute_final_rect(pet)
        self._tail_on_left = tail_left
        self._final_rect = rect
        self._base_pos = QPoint(rect.x(), rect.y())
        self.setGeometry(rect)
        self._state = "shown"
        self._position_close_button()
        self._close_btn.show()
        self.show()
        self.raise_()
        self._start_shake()

        self._hide_timer.stop()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms)

    def reposition(self) -> None:
        """Re-anchor next to the pet after the pet has moved."""
        if self._target is None or not self.isVisible() or self._state != "shown":
            return
        rect, tail_left = self._compute_final_rect(self._target)
        if tail_left != self._tail_on_left:
            self._tail_on_left = tail_left
            self.update()
        self._final_rect = rect
        self._base_pos = QPoint(rect.x(), rect.y())
        self.setGeometry(rect)
        self._position_close_button()

    def set_reply_callback(self, cb: Callable[[str], None] | None) -> None:
        self._reply_callback = cb

    # ---------- geometry ----------

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
        # Small negative gap so the tail visually pokes into the pet — reads
        # as "苏酱在说话" rather than a floating detached bubble.
        overlap = 8
        right_x = pet_geom.right() - overlap
        left_x = pet_geom.left() - total_w + overlap
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

    # ---------- attention shake ----------

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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            from macos_bridge import float_over_everything
        except ImportError:
            return
        float_over_everything(self, transient=True)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._hide_timer.stop()
        self._shake_timer.stop()
        self._state = "idle"
        self.closed.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._state == "shown":
            self._position_close_button()

    def paintEvent(self, _event) -> None:
        if self._state != "shown":
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        if self._tail_on_left:
            body = QRectF(TAIL, 0, w - TAIL, h)
        else:
            body = QRectF(0, 0, w - TAIL, h)
        path = QPainterPath()
        path.addRoundedRect(body, CORNER_R, CORNER_R)
        tail_y = h / 2
        tail = QPainterPath()
        if self._tail_on_left:
            tail.moveTo(body.left(), tail_y - TAIL)
            tail.lineTo(0, tail_y)
            tail.lineTo(body.left(), tail_y + TAIL)
        else:
            tail.moveTo(body.right(), tail_y - TAIL)
            tail.lineTo(w, tail_y)
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
        if self._state != "shown":
            return
        if event.button() == Qt.LeftButton and self._reply_callback is not None:
            text = self._text
            self.hide()
            self._reply_callback(text)
            return
        if event.button() == Qt.RightButton:
            self.hide()
