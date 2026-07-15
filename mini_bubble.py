"""Small ephemeral thought-cloud trail that fades in above the pet with an
encouragement phrase. Three clouds ascending diagonally (small → medium →
large), old-school 💭 comic-strip style. Text sits inside the largest cloud.
Fades in, holds, fades out. No close button, no click-to-chat — just a
passing thought."""
import math

from PyQt5.QtCore import (
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget

from encouragements import BUBBLE_FADE_IN_MS, BUBBLE_FADE_OUT_MS, BUBBLE_HOLD_MS

# --- cloud geometry ---
CLOUD_SMALL_R = 7         # tiny puff sitting on the pet's head-top
CLOUD_MED_R = 13          # middle puff, offset up-and-outward
CLOUD_BIG_ASPECT = 1.5    # big cloud width / height ratio — flatter, cloud-like
CLOUD_MIN_BIG_HALF_H = 26 # min semi-minor axis (half height) of the text cloud
CLOUD_MAX_BIG_HALF_H = 56 # cap so long phrases don't blow up the widget
CLOUD_TEXT_PAD = 8        # padding between inscribed text box and ellipse edge
CLOUD_GAP_1 = 4           # gap between small and medium (edge-to-edge)
CLOUD_GAP_2 = 6           # gap between medium and large
TRAIL_ANGLE_DEG = -62     # up-and-outward from pet; negative y = screen up
MAX_TEXT_WIDTH = 180      # word-wrap width used to size the big cloud
MARGIN = 5                # transparent widget padding so strokes don't clip

# --- warm-pink palette (softer than the amber reminder — a fond thought) ---
CLOUD_FILL = QColor(255, 224, 238, 245)
CLOUD_BORDER = QColor(240, 130, 175, 200)
TEXT_COLOR = QColor(150, 55, 105)


class MiniBubble(QWidget):
    """Fade-in / hold / fade-out three-cloud encouragement above the pet."""

    finished = pyqtSignal()

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
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._font = QFont("PingFang SC", 12)
        self._font.setWeight(QFont.Medium)
        self._text = ""
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._group: QSequentialAnimationGroup | None = None
        self._safety_timer = QTimer(self)
        self._safety_timer.setSingleShot(True)
        self._safety_timer.timeout.connect(self._safety_hide)

        # Cached layout for the current pop, in widget-local coords.
        self._small_c = QPointF(0.0, 0.0)
        self._med_c = QPointF(0.0, 0.0)
        self._big_c = QPointF(0.0, 0.0)
        self._big_a = float(CLOUD_MIN_BIG_HALF_H * CLOUD_BIG_ASPECT)  # semi-major (half-width)
        self._big_b = float(CLOUD_MIN_BIG_HALF_H)                     # semi-minor (half-height)

    def pop(self, pet, text: str) -> None:
        """Show `text` above `pet`'s head as a cloud trail, then auto-dismiss."""
        self._text = text
        rect = self._compute_layout(pet)
        self.setGeometry(rect)
        self._opacity.setOpacity(0.0)
        self.show()
        self.raise_()
        self._start_fade_sequence()

    # ---- layout ----

    def _big_ellipse_for_text(self) -> tuple[float, float]:
        """Size the big cloud as an ellipse with aspect CLOUD_BIG_ASPECT so
        `self._text` fits inscribed. Returns (semi_major_a, semi_minor_b)."""
        fm = QFontMetrics(self._font)
        text_bounds = fm.boundingRect(
            QRect(0, 0, MAX_TEXT_WIDTH, 400),
            int(Qt.TextWordWrap),
            self._text,
        )
        tw = text_bounds.width() + CLOUD_TEXT_PAD
        th = text_bounds.height() + CLOUD_TEXT_PAD
        # Text rectangle (tw × th) inscribed in ellipse (a, b) with a = k·b:
        # (tw/2a)² + (th/2b)² ≤ 1 ⇒ b² ≥ (tw/2k)² + (th/2)²
        k = CLOUD_BIG_ASPECT
        b = math.sqrt((tw / (2 * k)) ** 2 + (th / 2) ** 2)
        b = max(CLOUD_MIN_BIG_HALF_H, min(CLOUD_MAX_BIG_HALF_H, b))
        return (k * b, b)

    def _compute_layout(self, pet) -> QRect:
        """Compute widget rect + cache the three cloud centres in widget-local
        coords. Small cloud is centred on the pet's head anchor so it reads as
        a thought emanating from the head. Trail leans away from the closer
        screen edge so the big cloud with text stays on-screen."""
        pet_geom = pet.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry()
        # Direction: up-right when pet is on the left half, else up-left.
        trail_right = pet_geom.center().x() < screen.center().x()

        big_a, big_b = self._big_ellipse_for_text()
        self._big_a, self._big_b = big_a, big_b

        angle_rad = math.radians(TRAIL_ANGLE_DEG)
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)
        if not trail_right:
            dx = -dx  # mirror horizontal component only — still up

        # Ellipse radius along the trail direction (used for spacing to med cloud).
        # For axis-aligned ellipse: r(θ) = a·b / √((b·cos θ)² + (a·sin θ)²)
        theta = math.atan2(dy, dx)
        big_edge = (big_a * big_b) / math.hypot(
            big_b * math.cos(theta), big_a * math.sin(theta)
        )

        d1 = CLOUD_SMALL_R + CLOUD_GAP_1 + CLOUD_MED_R
        d2 = CLOUD_MED_R + CLOUD_GAP_2 + big_edge

        # Centres in a temporary frame with small cloud at origin.
        small = (0.0, 0.0)
        med = (small[0] + dx * d1, small[1] + dy * d1)
        big = (med[0] + dx * d2, med[1] + dy * d2)

        # Bounding box: small/med contribute a circle, big contributes ellipse extents.
        shapes = (
            (small[0] - CLOUD_SMALL_R, small[0] + CLOUD_SMALL_R,
             small[1] - CLOUD_SMALL_R, small[1] + CLOUD_SMALL_R),
            (med[0] - CLOUD_MED_R, med[0] + CLOUD_MED_R,
             med[1] - CLOUD_MED_R, med[1] + CLOUD_MED_R),
            (big[0] - big_a, big[0] + big_a, big[1] - big_b, big[1] + big_b),
        )
        min_x = min(s[0] for s in shapes) - MARGIN
        max_x = max(s[1] for s in shapes) + MARGIN
        min_y = min(s[2] for s in shapes) - MARGIN
        max_y = max(s[3] for s in shapes) + MARGIN
        widget_w = int(math.ceil(max_x - min_x))
        widget_h = int(math.ceil(max_y - min_y))

        # Store centres in widget-local coords.
        self._small_c = QPointF(small[0] - min_x, small[1] - min_y)
        self._med_c = QPointF(med[0] - min_x, med[1] - min_y)
        self._big_c = QPointF(big[0] - min_x, big[1] - min_y)

        # Anchor: small cloud CENTRE sits at the top-middle of the head so the
        # trail reads as thoughts perched right on the head-top.
        head_top = pet.head_top_point()
        widget_left = int(round(head_top.x() - self._small_c.x()))
        widget_top = int(round(head_top.y() - self._small_c.y()))

        # Clamp on-screen. If the big cloud would be clipped at the top, we
        # already flipped direction based on side; still need a floor for edge
        # cases where the pet is near the top of the screen.
        widget_left = max(screen.left(), min(widget_left, screen.right() - widget_w))
        widget_top = max(screen.top(), min(widget_top, screen.bottom() - widget_h))
        return QRect(widget_left, widget_top, widget_w, widget_h)

    # ---- fade sequence ----

    def _start_fade_sequence(self) -> None:
        if self._group is not None:
            self._group.stop()
        fade_in = QPropertyAnimation(self._opacity, b"opacity", self)
        fade_in.setDuration(BUBBLE_FADE_IN_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        fade_out = QPropertyAnimation(self._opacity, b"opacity", self)
        fade_out.setDuration(BUBBLE_FADE_OUT_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(fade_in)
        group.addPause(BUBBLE_HOLD_MS)
        group.addAnimation(fade_out)
        group.finished.connect(self._on_group_done)
        self._group = group
        group.start()

        total = BUBBLE_FADE_IN_MS + BUBBLE_HOLD_MS + BUBBLE_FADE_OUT_MS + 200
        self._safety_timer.start(total)

    def _on_group_done(self) -> None:
        self._safety_timer.stop()
        self.hide()
        self.finished.emit()

    def _safety_hide(self) -> None:
        if self.isVisible():
            self.hide()
            self.finished.emit()

    # ---- Qt events ----

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            from macos_bridge import float_over_everything
        except ImportError:
            return
        float_over_everything(self, transient=True)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(CLOUD_FILL)
        pen = QPen(CLOUD_BORDER, 1.4)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)

        # Draw the three clouds bottom→top so any (rare) overlap layers correctly.
        p.drawEllipse(self._small_c, CLOUD_SMALL_R, CLOUD_SMALL_R)
        p.drawEllipse(self._med_c, CLOUD_MED_R, CLOUD_MED_R)
        p.drawEllipse(self._big_c, self._big_a, self._big_b)

        # Text inscribed rectangle inside the big ellipse (corners at ±a/√2, ±b/√2).
        text_w = self._big_a * math.sqrt(2) - 4
        text_h = self._big_b * math.sqrt(2) - 4
        text_rect = QRectF(
            self._big_c.x() - text_w / 2,
            self._big_c.y() - text_h / 2,
            text_w,
            text_h,
        )
        p.setPen(TEXT_COLOR)
        p.setFont(self._font)
        p.drawText(
            text_rect,
            int(Qt.TextWordWrap | Qt.AlignCenter),
            self._text,
        )
