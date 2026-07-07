from typing import Callable

from PyQt5.QtCore import QPoint, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

PADDING = 14
TAIL = 10
CORNER_R = 12
MAX_TEXT_WIDTH = 240
CLOSE_BTN_SIZE = 22
# Warmer, attention-grabbing palette — feels like a real reminder note.
BG_COLOR = QColor(255, 249, 236, 245)
BORDER_COLOR = QColor(210, 155, 60, 140)
TEXT_COLOR = QColor(50, 40, 20)
SHAKE_FRAMES = ((6, 0), (-6, 0), (5, 0), (-5, 0), (3, 0), (-3, 0), (0, 0))
SHAKE_INTERVAL_MS = 55


class SpeechBubble(QWidget):
    """Frameless, translucent bubble that appears next to a target widget.
    Emits `closed` whenever the bubble is hidden — so callers can restore state
    (e.g., pet returning from `waving` to `idle`)."""

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
        self._target: QWidget | None = None
        self._reply_callback: Callable[[str], None] | None = None
        self._base_pos = QPoint(0, 0)
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
        self._close_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent;"
            " color: rgba(90, 60, 30, 200); font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { color: #c0392b; }"
        )
        self._close_btn.clicked.connect(self.hide)

    def show_next_to(self, target: QWidget, text: str, duration_ms: int = 0) -> None:
        """Show the bubble anchored to `target`. duration_ms=0 means never
        auto-hide — the user must dismiss it via the × button."""
        self._text = text
        self._target = target
        fm = QFontMetrics(self._font)
        text_rect = fm.boundingRect(
            QRect(0, 0, MAX_TEXT_WIDTH, 400),
            int(Qt.TextWordWrap),
            text,
        )
        body_w = max(140, text_rect.width() + 2 * PADDING + CLOSE_BTN_SIZE)
        body_h = max(56, text_rect.height() + 2 * PADDING)
        self.resize(body_w + TAIL, body_h)
        self._reposition_for(target)
        self._position_close_button()
        self.show()
        self.raise_()
        self._start_shake()
        self._hide_timer.stop()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms)

    def reposition(self) -> None:
        """Re-anchor to the last target (called when the target widget moves)."""
        if self._target is not None and self.isVisible():
            self._reposition_for(self._target)

    def _reposition_for(self, target: QWidget) -> None:
        geom = target.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry()
        right_x = geom.right() + 6
        left_x = geom.left() - self.width() - 6
        if right_x + self.width() <= screen.right():
            x = right_x
            need_left_tail = True
        else:
            x = max(screen.left(), left_x)
            need_left_tail = False
        y = geom.center().y() - self.height() // 2
        y = max(screen.top(), min(y, screen.bottom() - self.height()))
        if need_left_tail != self._tail_on_left:
            self._tail_on_left = need_left_tail
            self._position_close_button()
            self.update()
        self._base_pos = QPoint(x, y)
        self.move(self._base_pos)

    def _position_close_button(self) -> None:
        body_right = self.width() - (TAIL if not self._tail_on_left else 0)
        self._close_btn.move(body_right - CLOSE_BTN_SIZE - 4, 4)

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

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._hide_timer.stop()
        self._shake_timer.stop()
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
        right_pad = PADDING + CLOSE_BTN_SIZE  # leave room for the × button
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

    def set_reply_callback(self, cb: Callable[[str], None] | None) -> None:
        self._reply_callback = cb

    def mousePressEvent(self, event) -> None:
        # Left-click body opens the chat (if a callback is set); right-click closes.
        if event.button() == Qt.LeftButton and self._reply_callback is not None:
            text = self._text
            self.hide()
            self._reply_callback(text)
            return
        if event.button() == Qt.RightButton:
            self.hide()
