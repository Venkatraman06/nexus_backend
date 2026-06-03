JAZZMIN_SETTINGS = {
    "site_title": "PMT Admin",
    "site_header": "PMO Platform",
    "site_brand": "PMT",
    "site_logo": None,
    "login_logo": None,
    "site_icon": None,
    "welcome_sign": "Welcome to the PMO Platform Admin",
    "copyright": "Impiger Technologies",
    "search_model": ["accounts.Employee", "projects.Project"],
    "user_avatar": "profile_picture",

    ############
    # Top Menu #
    ############
    "topmenu_links": [
        {"name": "Home",          "url": "admin:index"},
        {"name": "API Docs",      "url": "/pmt/api/docs/",   "new_window": True},
        {"name": "API Schema",    "url": "/pmt/api/redoc/",  "new_window": True},
    ],

    #############
    # Side Menu #
    #############
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": ["auth"],
    "hide_models": [
        "django_celery_beat.SolarSchedule",
        "django_celery_results.ChordCounter",
        "django_celery_results.GroupResult",
    ],
    "order_with_respect_to": [
        "accounts",
        "projects",
        "workitems",
        "allocation",
        "pmt_workflow",
        "django_celery_beat",
        "django_celery_results",
    ],

    #########
    # Icons #
    #########
    "icons": {
        "accounts.Employee":             "fas fa-users",
        "accounts.EmployeeCertificate":  "fas fa-certificate",
        "projects.Client":               "fas fa-building",
        "projects.Project":              "fas fa-project-diagram",
        "projects.Epic":                 "fas fa-layer-group",
        "projects.Story":                "fas fa-book-open",
        "workitems.WorkItem":            "fas fa-tasks",
        "workitems.WorkLog":             "fas fa-clock",
        "workitems.WorkItemAttachment":  "fas fa-paperclip",
        "allocation.Allocation":         "fas fa-user-check",
        "pmt_workflow.State":            "fas fa-stream",
        "pmt_workflow.Transition":       "fas fa-random",
        "pmt_workflow.Proceeding":       "fas fa-history",
        "django_celery_beat.PeriodicTask":    "fas fa-calendar-alt",
        "django_celery_beat.CrontabSchedule": "fas fa-cogs",
        "django_celery_results.TaskResult":   "fas fa-check-circle",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    #################
    # Related Modal #
    #################
    "related_modal_active": True,

    #############
    # UI Tweaks #
    #############
    "custom_css": None,
    "custom_js":  None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,

    ###############
    # Change view #
    ###############
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text":   False,
    "brand_small_text":  False,
    "brand_colour":      "navbar-primary",
    "accent":            "accent-primary",
    "navbar":            "navbar-dark",
    "no_navbar_border":  False,
    "navbar_fixed":      True,
    "layout_boxed":      False,
    "footer_fixed":      False,
    "sidebar_fixed":     True,
    "sidebar":           "sidebar-dark-primary",
    "sidebar_nav_small_text":    False,
    "sidebar_disable_expand":    False,
    "sidebar_nav_child_indent":  False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style":  False,
    "sidebar_nav_flat_style":    False,
    "theme":          "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary":   "btn-primary",
        "secondary": "btn-secondary",
        "info":      "btn-info",
        "warning":   "btn-warning",
        "danger":    "btn-danger",
        "success":   "btn-success",
    },
}
