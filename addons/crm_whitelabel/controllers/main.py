from odoo import http
from odoo.http import request, root
from odoo.addons.web.controllers.home import Home

SESSION_1_YEAR = 365 * 24 * 60 * 60

if hasattr(http, 'SESSION_LIFETIME'):
    http.SESSION_LIFETIME = SESSION_1_YEAR

if hasattr(root, 'session_store') and root.session_store:
    root.session_store.session_timeout = SESSION_1_YEAR

class CrmWhitelabelController(http.Controller):
    @http.route(['/favicon.ico'], type='http', auth='public', website=True, multilang=False, sitemap=False, readonly=True)
    def favicon(self, **kw):
        return request.redirect('/web/static/img/favicon.ico', code=301)

    @http.route('/crm/dashboard-preview', type='http', auth='public', website=False)
    def dashboard_preview(self, **kw):
        return request.render('crm_whitelabel.dashboard_preview_template', {})

    @http.route('/crm/analytics', type='http', auth='user', website=False)
    def crm_analytics(self, **kw):
        action = request.env.ref('crm_whitelabel.action_crm_analytics_dashboard', raise_if_not_found=False)
        action_id = action.id if action else ''
        return request.redirect(f'/web#action={action_id}')

    @http.route('/crm/user/get_profile', type='json', auth='user')
    def get_user_profile(self):
        user = request.env.user
        partner = user.partner_id
        return {
            'id': user.id,
            'name': user.name or '',
            'login': user.login or '',
            'email': user.email or partner.email or '',
            'phone': partner.phone or '',
            'mobile': partner.mobile or '',
            'image_128': user.image_128.decode('utf-8') if user.image_128 else False,
            'job_title': (getattr(user, 'crm_job_id', None) and user.crm_job_id.name) or (getattr(user, 'employee_id', None) and user.employee_id.job_title) or '',
            'department': (getattr(user, 'crm_department_id', None) and user.crm_department_id.name) or (getattr(user, 'employee_id', None) and user.employee_id.department_id and user.employee_id.department_id.name) or '',
            'manager': (getattr(user, 'crm_manager_id', None) and user.crm_manager_id.name) or (getattr(user, 'employee_id', None) and user.employee_id.parent_id and user.employee_id.parent_id.name) or '',
            'expense_manager': (getattr(user, 'crm_expense_manager_id', None) and user.crm_expense_manager_id.name) or '',
        }

    @http.route('/crm/user/save_profile', type='json', auth='user')
    def save_user_profile(self, name=None, email=None, phone=None, mobile=None):
        user = request.env.user
        partner = user.partner_id
        user_vals = {}
        partner_vals = {}

        if name:
            user_vals['name'] = name.strip()
            partner_vals['name'] = name.strip()
        if email is not None:
            user_vals['email'] = email.strip()
            partner_vals['email'] = email.strip()
        if phone is not None:
            partner_vals['phone'] = phone.strip()
        if mobile is not None:
            partner_vals['mobile'] = mobile.strip()

        if user_vals:
            user.sudo().write(user_vals)
        if partner_vals:
            partner.sudo().write(partner_vals)

        return {'success': True}

class PersistentHome(Home):
    @http.route('/', type='http', auth="none")
    def index(self, s_action=None, **kw):
        if request.session.uid:
            return request.redirect('/app/action-435')
        return super(PersistentHome, self).index(s_action=s_action, **kw)

    @http.route('/web/login', type='http', auth="public", sitemap=False)
    def web_login(self, redirect=None, **kw):
        if request.session.uid and not redirect:
            return request.redirect('/app/action-435')
        
        response = super(PersistentHome, self).web_login(redirect=redirect, **kw)
        
        if request and request.session and request.session.uid:
            try:
                request.future_response.set_cookie('session_id', request.session.sid, max_age=SESSION_1_YEAR, httponly=True)
            except Exception:
                pass
                
        return response
