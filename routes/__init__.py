"""routes 패키지 — Blueprint 중앙 등록"""


def register_blueprints(app):
    from routes.auth import auth_bp
    from routes.apply import apply_bp
    from routes.admin import admin_bp
    from routes.attendance import attendance_bp
    from routes.payslip import payslip_bp
    from routes.advance import advance_bp
    from routes.employee import employee_bp
    from routes.dashboard import dashboard_bp
    from routes.site import site_bp
    from routes.notice import notice_bp
    from routes.contract import contract_bp
    from routes.leave import leave_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(apply_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(payslip_bp)
    app.register_blueprint(advance_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(site_bp)
    app.register_blueprint(notice_bp)
    app.register_blueprint(contract_bp)
    app.register_blueprint(leave_bp)
