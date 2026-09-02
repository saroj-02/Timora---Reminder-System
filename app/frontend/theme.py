"""
Timora – Design Theme

Central place for:
- colors
- typography
- layout
- sidebar
- navigation
- cards
- responsive behavior
- global CSS
"""

from __future__ import annotations

from nicegui import ui


# ============================================================================
# Color Palette
# ============================================================================

PURPLE = "#7C3AED"
PURPLE_LIGHT = "#A78BFA"
PURPLE_DARK = "#5B21B6"

BLUE = "#2563EB"
BLUE_LIGHT = "#60A5FA"

CYAN = "#06B6D4"
CYAN_LIGHT = "#67E8F9"

DARK_BG = "#0B1020"
DARK_SURFACE = "#0D1324"
DARK_CARD = "#151E33"
DARK_BORDER = "#26324A"

DARK_TEXT = "#F1F5F9"
DARK_MUTED = "#94A3B8"

LIGHT_BG = "#F6F8FC"
LIGHT_SURFACE = "#FFFFFF"
LIGHT_CARD = "#FFFFFF"
LIGHT_BORDER = "#E2E8F0"

LIGHT_TEXT = "#172033"
LIGHT_MUTED = "#64748B"

SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#EF4444"
INFO = "#3B82F6"


# ============================================================================
# Global CSS
# ============================================================================

GLOBAL_CSS = r"""
/* =========================================================================
   Base
   ========================================================================= */

html,
body {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;

    overflow-x: hidden !important;

    background: #0B1020;
}

body {
    font-family: 'Inter', sans-serif !important;
    color: #F1F5F9;

    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}

*,
*::before,
*::after {
    box-sizing: border-box !important;
}


/* =========================================================================
   NiceGUI / Quasar overflow protection
   ========================================================================= */

.q-layout,
.q-page-container,
.q-page,
.nicegui-content,
.q-drawer,
.q-header,
.q-footer {
    min-width: 0 !important;
    max-width: 100vw !important;
}

.q-page-container {
    overflow-x: hidden !important;
}

.nicegui-content {
    overflow-x: hidden !important;
}


/* =========================================================================
   Header
   ========================================================================= */

.timora-header {
    position: fixed !important;

    top: 0 !important;
    left: 0 !important;
    right: 0 !important;

    height: 72px !important;

    z-index: 2000 !important;

    padding: 0 28px !important;

    background: rgba(11, 16, 32, 0.94) !important;

    border-bottom: 1px solid rgba(148, 163, 184, 0.12) !important;

    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
}


/* =========================================================================
   Brand
   ========================================================================= */

.timora-brand {
    gap: 12px !important;
}

.timora-brand-icon {
    width: 42px !important;
    height: 42px !important;

    display: flex !important;
    align-items: center !important;
    justify-content: center !important;

    border-radius: 12px !important;

    font-size: 22px !important;

    background: linear-gradient(
        135deg,
        #7C3AED,
        #2563EB
    ) !important;

    box-shadow:
        0 8px 24px rgba(124, 58, 237, 0.28);
}

.timora-brand-name {
    font-size: 21px !important;
    font-weight: 800 !important;

    background: linear-gradient(
        135deg,
        #A78BFA,
        #60A5FA
    );

    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}


/* =========================================================================
   Header User
   ========================================================================= */

.timora-user-area {
    gap: 10px !important;
}

.timora-user-name {
    color: #CBD5E1 !important;

    font-size: 14px !important;
    font-weight: 600 !important;

    white-space: nowrap !important;
}

.timora-logout {
    color: #94A3B8 !important;

    transition:
        color 0.2s ease,
        background 0.2s ease,
        transform 0.2s ease !important;
}

.timora-logout:hover {
    color: #F1F5F9 !important;

    background: rgba(124, 58, 237, 0.12) !important;

    transform: translateX(2px);
}


/* =========================================================================
   Desktop Sidebar
   ========================================================================= */

.sidebar {
    width: 238px !important;

    top: 72px !important;
    height: calc(100vh - 72px) !important;

    background: #0D1324 !important;

    border-right: 1px solid rgba(148, 163, 184, 0.12) !important;

    overflow: hidden !important;
}

.sidebar-inner {
    width: 100% !important;
    height: 100% !important;

    padding: 34px 8px 20px !important;

    display: flex !important;
    flex-direction: column !important;

    overflow: hidden !important;
}


/* =========================================================================
   Sidebar Heading
   ========================================================================= */

.sidebar-heading {
    margin: 0 12px 14px !important;

    color: #64748B !important;

    font-size: 10px !important;
    font-weight: 800 !important;

    letter-spacing: 1.3px !important;
}


/* =========================================================================
   Sidebar Navigation
   ========================================================================= */

.sidebar-navigation {
    width: 100% !important;

    display: flex !important;
    flex-direction: column !important;

    gap: 5px !important;
}


/*
   IMPORTANT:
   Compact navigation.

   Previous version:
       padding: 10px 16px
       margin-bottom: 4px

   This caused unnecessary vertical spacing.

   New version:
       min-height: 44px
       padding: 9px 12px
       gap: 10px
       navigation gap: 5px
*/

.sidebar-item {
    width: 100% !important;
    min-height: 44px !important;

    display: flex !important;
    align-items: center !important;

    padding: 9px 12px !important;

    gap: 10px !important;

    border-radius: 11px !important;

    cursor: pointer !important;

    color: #94A3B8 !important;

    transition:
        background 0.18s ease,
        color 0.18s ease,
        transform 0.18s ease,
        border-color 0.18s ease !important;

    border: 1px solid transparent !important;

    user-select: none !important;
}

.sidebar-item:hover {
    background: rgba(124, 58, 237, 0.10) !important;

    color: #E2E8F0 !important;

    transform: translateX(2px);
}

.sidebar-item.active {
    background: linear-gradient(
        135deg,
        rgba(124, 58, 237, 0.23),
        rgba(37, 99, 235, 0.15)
    ) !important;

    border-color: rgba(
        124,
        58,
        237,
        0.28
    ) !important;

    color: #F1F5F9 !important;

    box-shadow:
        0 8px 24px rgba(76, 29, 149, 0.16);
}


/* =========================================================================
   Sidebar Icon
   ========================================================================= */

.sidebar-item-icon {
    flex: 0 0 20px !important;

    color: #64748B !important;

    transition:
        color 0.18s ease,
        transform 0.18s ease !important;
}

.sidebar-item:hover .sidebar-item-icon {
    color: #A78BFA !important;

    transform: scale(1.04);
}

.sidebar-item.active .sidebar-item-icon {
    color: #A78BFA !important;
}


/* =========================================================================
   Sidebar Label
   ========================================================================= */

.sidebar-item-label {
    min-width: 0 !important;

    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;

    color: inherit !important;

    font-size: 14px !important;
    font-weight: 500 !important;

    line-height: 1 !important;
}

.sidebar-item.active .sidebar-item-label {
    font-weight: 650 !important;
}


/* =========================================================================
   Sidebar Notification Status
   ========================================================================= */

.sidebar-status {
    width: 100% !important;

    padding: 13px 12px !important;

    border-radius: 12px !important;

    background: rgba(
        148,
        163,
        184,
        0.035
    ) !important;

    border: 1px solid rgba(
        148,
        163,
        184,
        0.09
    ) !important;
}

.sidebar-status .q-row {
    gap: 9px !important;
}

.sidebar-status-icon {
    color: #34D399 !important;
}

.sidebar-status-icon.disabled {
    color: #64748B !important;
}

.sidebar-status-text {
    gap: 2px !important;
}

.sidebar-status-title {
    color: #CBD5E1 !important;

    font-size: 11px !important;
    font-weight: 650 !important;
}

.sidebar-status-value {
    color: #34D399 !important;

    font-size: 10px !important;
    font-weight: 500 !important;
}

.sidebar-status-value.disabled {
    color: #64748B !important;
}


/* =========================================================================
   Main Content
   ========================================================================= */

.main-content {
    width: min(
        calc(100% - 40px),
        1240px
    ) !important;

    max-width: 1240px !important;

    /*
     * IMPORTANT:
     * NiceGUI/Quasar already reserves the drawer width.
     * Do NOT add another 238px/262px margin here.
     */
    margin-left: 5px !important;
    margin-right: 5px !important;

    padding-top: 104px !important;
    padding-bottom: 48px !important;

    min-width: 0 !important;
    max-width: calc(100% - 40px) !important;

    overflow-x: hidden !important;
}

/* =========================================================================
   Page
   ========================================================================= */

.page-enter {
    animation:
        pageIn 0.28s ease both;
}

@keyframes pageIn {
    from {
        opacity: 0;
        transform: translateY(8px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}


/* =========================================================================
   Page Typography
   ========================================================================= */

.page-title {
    font-size: clamp(
        24px,
        3vw,
        32px
    ) !important;

    line-height: 1.2 !important;

    font-weight: 800 !important;

    color: #F1F5F9 !important;
}

.page-subtitle {
    margin-top: 7px !important;

    color: #94A3B8 !important;

    font-size: 14px !important;
}


/* =========================================================================
   Cards
   ========================================================================= */

.q-card {
    max-width: 100% !important;

    overflow: hidden;
}

.glass-card {
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);

    border: 1px solid rgba(
        255,
        255,
        255,
        0.08
    );
}


/* =========================================================================
   Primary Button
   ========================================================================= */

.btn-primary {
    background: linear-gradient(
        135deg,
        #7C3AED,
        #2563EB
    ) !important;

    border: none !important;

    border-radius: 11px !important;

    font-weight: 650 !important;

    letter-spacing: 0.2px !important;

    min-height: 42px !important;

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease !important;

    box-shadow:
        0 8px 24px rgba(
            124,
            58,
            237,
            0.25
        ) !important;
}

.btn-primary:hover {
    transform: translateY(-2px) !important;

    box-shadow:
        0 12px 30px rgba(
            124,
            58,
            237,
            0.35
        ) !important;
}


/* =========================================================================
   Stat Grid
   ========================================================================= */

.stat-grid {
    width: 100% !important;

    display: grid !important;

    grid-template-columns:
        repeat(
            4,
            minmax(0, 1fr)
        ) !important;

    gap: 16px !important;
}

.stat-card {
    min-width: 0 !important;

    padding: 20px !important;

    border-radius: 18px !important;

    background: #151E33 !important;

    border: 1px solid #26324A !important;

    position: relative !important;

    overflow: hidden !important;

    transition:
        transform 0.2s ease,
        border-color 0.2s ease,
        box-shadow 0.2s ease !important;
}

.stat-card:hover {
    transform: translateY(-3px);

    border-color:
        rgba(139, 92, 246, 0.45) !important;

    box-shadow:
        0 14px 35px rgba(0, 0, 0, 0.18);
}

.stat-card::before {
    content: '';

    position: absolute;

    top: 0;
    left: 0;
    right: 0;

    height: 3px;
}

.stat-total::before {
    background:
        linear-gradient(
            90deg,
            #7C3AED,
            #A78BFA
        );
}

.stat-today::before {
    background:
        linear-gradient(
            90deg,
            #2563EB,
            #60A5FA
        );
}

.stat-upcoming::before {
    background:
        linear-gradient(
            90deg,
            #06B6D4,
            #67E8F9
        );
}

.stat-completed::before {
    background:
        linear-gradient(
            90deg,
            #10B981,
            #34D399
        );
}

.stat-value {
    font-size: 30px !important;

    font-weight: 800 !important;

    line-height: 1 !important;
}

.stat-title {
    margin-top: 8px !important;

    color: #94A3B8 !important;

    font-size: 13px !important;

    font-weight: 500 !important;
}


/* =========================================================================
   Reminder Cards
   ========================================================================= */

.reminder-card {
    width: 100% !important;

    min-width: 0 !important;

    border-radius: 16px !important;

    background: #151E33 !important;

    border: 1px solid #26324A !important;

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease,
        border-color 0.2s ease !important;
}

.reminder-card:hover {
    transform: translateY(-2px);

    border-color:
        rgba(
            139,
            92,
            246,
            0.35
        ) !important;

    box-shadow:
        0 12px 30px rgba(
            0,
            0,
            0,
            0.16
        );
}

.reminder-card.completed {
    opacity: 0.68;
}


/* =========================================================================
   Priority
   ========================================================================= */

.priority-high {
    background: rgba(
        239,
        68,
        68,
        0.15
    );

    color: #EF4444;
}

.priority-medium {
    background: rgba(
        245,
        158,
        11,
        0.15
    );

    color: #F59E0B;
}

.priority-low {
    background: rgba(
        16,
        185,
        129,
        0.15
    );

    color: #10B981;
}


/* =========================================================================
   Status
   ========================================================================= */

.status-pending {
    background: rgba(
        37,
        99,
        235,
        0.15
    );

    color: #60A5FA;
}

.status-sent {
    background: rgba(
        6,
        182,
        212,
        0.15
    );

    color: #67E8F9;
}

.status-completed {
    background: rgba(
        16,
        185,
        129,
        0.15
    );

    color: #10B981;
}

.status-snoozed {
    background: rgba(
        245,
        158,
        11,
        0.15
    );

    color: #F59E0B;
}


/* =========================================================================
   Empty State
   ========================================================================= */

.empty-state {
    width: 100% !important;

    min-height: 170px !important;

    padding: 34px 20px !important;

    border-radius: 16px !important;

    border: 1px dashed rgba(
        100,
        116,
        139,
        0.25
    ) !important;

    background:
        rgba(
            15,
            23,
            42,
            0.28
        ) !important;

    display: flex !important;

    align-items: center !important;
    justify-content: center !important;
}


/* =========================================================================
   Calendar
   ========================================================================= */

.calendar-day {
    min-width: 0 !important;

    min-height: 80px !important;

    border-radius: 10px !important;

    cursor: pointer;

    transition:
        background 0.2s ease,
        border-color 0.2s ease,
        transform 0.2s ease !important;
}

.calendar-day:hover {
    background:
        rgba(
            124,
            58,
            237,
            0.10
        ) !important;

    transform: translateY(-1px);
}

.calendar-day.has-reminders {
    border-left:
        3px solid #7C3AED;
}

.calendar-day.today {
    background:
        rgba(
            124,
            58,
            237,
            0.15
        ) !important;

    font-weight: 700;
}


/* =========================================================================
   Search
   ========================================================================= */

.search-input {
    width: 100% !important;

    min-width: 0 !important;

    border-radius: 12px !important;
}


/* =========================================================================
   Input focus
   ========================================================================= */

.q-field--focused .q-field__control {
    border-color:
        #7C3AED !important;

    box-shadow:
        0 0 0 3px
        rgba(
            124,
            58,
            237,
            0.16
        ) !important;
}


/* =========================================================================
   Reminder Popup
   ========================================================================= */

@keyframes popupIn {
    from {
        opacity: 0;

        transform:
            scale(0.96)
            translateY(10px);
    }

    to {
        opacity: 1;

        transform:
            scale(1)
            translateY(0);
    }
}

.reminder-popup {
    animation:
        popupIn
        0.28s ease;

    border-radius: 18px !important;

    background:
        linear-gradient(
            135deg,
            #151E33,
            #111827
        );

    border:
        1px solid
        rgba(
            124,
            58,
            237,
            0.40
        );

    box-shadow:
        0 24px 70px
        rgba(
            0,
            0,
            0,
            0.50
        );
}


/* =========================================================================
   Toast
   ========================================================================= */

.timora-toast {
    border-radius: 12px;

    backdrop-filter: blur(20px);

    font-weight: 500;
}


/* =========================================================================
   Scrollbars
   ========================================================================= */

::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: transparent;
}

::-webkit-scrollbar-thumb {
    background:
        rgba(
            124,
            58,
            237,
            0.35
        );

    border-radius: 99px;
}

::-webkit-scrollbar-thumb:hover {
    background:
        rgba(
            124,
            58,
            237,
            0.65
        );
}


/* =========================================================================
   Mobile Navigation
   ========================================================================= */

.mobile-nav {
    display: none !important;
}

.mobile-nav-item {
    flex: 1 !important;

    min-width: 0 !important;

    height: 54px !important;

    display: flex !important;

    flex-direction: column !important;

    align-items: center !important;

    justify-content: center !important;

    gap: 3px !important;

    border-radius: 10px !important;

    cursor: pointer !important;

    color: #64748B !important;

    transition:
        background 0.18s ease,
        color 0.18s ease !important;
}

.mobile-nav-item:hover {
    background:
        rgba(
            124,
            58,
            237,
            0.08
        ) !important;
}

.mobile-nav-item.active {
    background:
        rgba(
            124,
            58,
            237,
            0.14
        ) !important;

    color: #A78BFA !important;
}

.mobile-nav-icon {
    color: inherit !important;
}

.mobile-nav-label {
    color: inherit !important;

    font-size: 10px !important;

    font-weight: 600 !important;

    line-height: 1 !important;
}


/* =========================================================================
   Responsive: Medium screens
   ========================================================================= */

@media (max-width: 1100px) {

    .sidebar {
        width: 210px !important;
    }

    .main-content {
        width: calc(100% - 32px) !important;

        max-width: none !important;

        margin-left: 16px !important;
        margin-right: 16px !important;
    }

    .stat-grid {
        grid-template-columns:
            repeat(
                2,
                minmax(0, 1fr)
            ) !important;

        gap: 14px !important;
    }
}


/* =========================================================================
   Responsive: Mobile
   ========================================================================= */

@media (max-width: 768px) {

    html,
    body {
        overflow-x: hidden !important;
    }

    .timora-header {
        height: 64px !important;

        padding:
            0 16px !important;
    }

    .timora-brand-icon {
        width: 38px !important;
        height: 38px !important;

        font-size: 20px !important;
    }

    .timora-brand-name {
        font-size: 19px !important;
    }

    .timora-user-name {
        max-width: 130px !important;

        overflow: hidden !important;

        text-overflow: ellipsis !important;
    }

    .sidebar {
        display: none !important;
    }

    .main-content {
        width: calc(
            100% - 28px
        ) !important;

        max-width: none !important;

        margin-left: 14px !important;
        margin-right: 14px !important;

        padding-top: 88px !important;
        padding-bottom: 92px !important;
    }

    .mobile-nav {
        position: fixed !important;

        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;

        min-height: 68px !important;

        display: flex !important;

        align-items: center !important;

        gap: 5px !important;

        padding:
            7px 8px !important;

        background:
            rgba(
                13,
                19,
                36,
                0.97
            ) !important;

        border-top:
            1px solid
            rgba(
                148,
                163,
                184,
                0.12
            ) !important;

        backdrop-filter: blur(18px);

        z-index: 3000 !important;
    }

    .stat-grid {
        grid-template-columns:
            repeat(
                2,
                minmax(0, 1fr)
            ) !important;

        gap: 12px !important;
    }

    .page-title {
        font-size: 25px !important;
    }
}


/* =========================================================================
   Responsive: Small mobile
   ========================================================================= */

@media (max-width: 520px) {

    .timora-user-name {
        display: none !important;
    }

    .main-content {
        width: calc(
            100% - 20px
        ) !important;

        margin-left: 10px !important;
        margin-right: 10px !important;
    }

    .stat-grid {
        grid-template-columns:
            1fr !important;
    }

    .stat-card {
        padding: 17px !important;
    }

    .mobile-nav-item {
        height: 52px !important;
    }

    .mobile-nav-label {
        font-size: 9px !important;
    }
}
"""


# ============================================================================
# Dark Theme
# ============================================================================

DARK_THEME_CSS = r"""
body,
.q-layout,
.q-page,
.q-page-container,
.nicegui-content {
    background: #0B1020 !important;
    color: #F1F5F9 !important;
}

.q-card {
    background: #151E33 !important;

    color: #F1F5F9 !important;

    border-color:
        #26324A !important;
}

.q-drawer {
    background: #0D1324 !important;

    border-color:
        rgba(
            148,
            163,
            184,
            0.12
        ) !important;
}

.q-field__native,
.q-field__input {
    color: #F1F5F9 !important;
}

.q-field__label {
    color: #94A3B8 !important;
}

.q-field__marginal {
    color: #94A3B8 !important;
}

.q-checkbox__label,
.q-toggle__label {
    color: #CBD5E1 !important;
}

.q-menu {
    background: #151E33 !important;

    color: #F1F5F9 !important;
}

.q-item {
    color: #CBD5E1 !important;
}
"""


# ============================================================================
# Light Theme
# ============================================================================

LIGHT_THEME_CSS = r"""
body,
.q-layout,
.q-page,
.q-page-container,
.nicegui-content {
    background: #F6F8FC !important;

    color: #172033 !important;
}

.q-card {
    background: #FFFFFF !important;

    color: #172033 !important;

    border-color:
        #E2E8F0 !important;
}

.q-drawer {
    background: #FFFFFF !important;

    border-color:
        #E2E8F0 !important;
}

.timora-header {
    background:
        rgba(
            255,
            255,
            255,
            0.94
        ) !important;

    border-bottom-color:
        #E2E8F0 !important;
}

.page-title,
.section-heading,
.reminder-title {
    color: #172033 !important;
}

.page-subtitle,
.stat-title,
.reminder-meta {
    color: #64748B !important;
}

.q-field__native,
.q-field__input {
    color: #172033 !important;
}

.q-field__label {
    color: #64748B !important;
}

.sidebar-item {
    color: #64748B !important;
}

.sidebar-item:hover {
    background:
        rgba(
            124,
            58,
            237,
            0.07
        ) !important;

    color: #4C1D95 !important;
}

.sidebar-item.active {
    color: #4C1D95 !important;

    background:
        rgba(
            124,
            58,
            237,
            0.09
        ) !important;
}

.sidebar-item-icon {
    color: #64748B !important;
}

.sidebar-item.active .sidebar-item-icon {
    color: #7C3AED !important;
}

.sidebar-status {
    background:
        rgba(
            15,
            23,
            42,
            0.025
        ) !important;

    border-color:
        #E2E8F0 !important;
}

.empty-state {
    background: #FFFFFF !important;

    border-color:
        #CBD5E1 !important;
}

.q-menu {
    background: #FFFFFF !important;

    color: #172033 !important;
}
"""


# ============================================================================
# Style Injection
# ============================================================================

def inject_global_styles() -> None:
    """
    Inject global application CSS.

    Call once when the application starts.
    """

    ui.add_head_html(
        f"""
        <style>
        {GLOBAL_CSS}
        </style>

        <link
            rel="preconnect"
            href="https://fonts.googleapis.com"
        >

        <link
            rel="preconnect"
            href="https://fonts.gstatic.com"
            crossorigin
        >

        <link
            href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;650;700;800&display=swap"
            rel="stylesheet"
        >

        <link
            href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet"
        >

        <link
            href="https://fonts.googleapis.com/icon?family=Material+Icons+Outlined"
            rel="stylesheet"
        >

        <link
            rel="manifest"
            href="/static/manifest.json"
        >

        <meta
            name="theme-color"
            content="#0B1020"
        >

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >
        """
    )


def inject_theme(theme: str = "dark") -> None:
    """
    Inject the selected application theme.

    Supported values:
        dark
        light
    """

    css = (
        LIGHT_THEME_CSS
        if theme == "light"
        else DARK_THEME_CSS
    )

    ui.add_head_html(
        f"""
        <style>
        {css}
        </style>
        """
    )