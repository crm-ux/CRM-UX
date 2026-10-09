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
    def get_user_profile(self, user_id=None):
        try:
            target_uid = int(user_id) if user_id else request.env.user.id
            user = request.env['res.users'].sudo().browse(target_uid)
            if not user.exists():
                user = request.env.user.sudo()

            partner = user.partner_id.sudo() if user.partner_id else False
            
            # Find linked employee directly by user_id or employee_id
            emp = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not emp and getattr(user, 'employee_id', None) and user.employee_id:
                emp = user.employee_id.sudo()

            img_str = False
            if user.image_128:
                try:
                    img_val = user.image_128
                    if isinstance(img_val, bytes):
                        img_str = img_val.decode('ascii')
                    elif isinstance(img_val, str):
                        img_str = img_val
                except Exception:
                    img_str = False

            email_val = (partner and partner.email) or user.email or (emp and emp.work_email) or ''
            phone_val = (partner and partner.phone) or getattr(user, 'phone', None) or (emp and emp.work_phone) or ''
            mobile_val = (partner and partner.mobile) or getattr(user, 'mobile', None) or (emp and emp.mobile_phone) or ''

            # Job position
            job_title = ''
            if getattr(user, 'crm_job_id', None) and user.crm_job_id:
                job_title = user.crm_job_id.name or ''
            elif emp and emp.job_id:
                job_title = emp.job_id.name or ''
            elif emp and emp.job_title:
                job_title = emp.job_title or ''

            # Department
            department = ''
            if getattr(user, 'crm_department_id', None) and user.crm_department_id:
                department = user.crm_department_id.name or ''
            elif emp and emp.department_id:
                department = emp.department_id.name or ''

            # Manager
            manager = ''
            if getattr(user, 'crm_manager_id', None) and user.crm_manager_id:
                manager = user.crm_manager_id.name or ''
            elif emp and emp.parent_id:
                manager = emp.parent_id.name or ''

            # Expense manager
            expense_manager = ''
            if getattr(user, 'crm_expense_manager_id', None) and user.crm_expense_manager_id:
                expense_manager = user.crm_expense_manager_id.name or ''

            return {
                'id': user.id,
                'name': user.name or (partner and partner.name) or (emp and emp.name) or '',
                'login': user.login or '',
                'email': email_val,
                'phone': phone_val,
                'mobile': mobile_val,
                'image_128': img_str,
                'job_title': job_title,
                'department': department,
                'manager': manager,
                'expense_manager': expense_manager,
            }
        except Exception as e:
            return {
                'id': request.env.user.id,
                'name': request.env.user.name or '',
                'login': request.env.user.login or '',
                'email': request.env.user.email or '',
                'phone': '',
                'mobile': '',
                'image_128': False,
                'job_title': '',
                'department': '',
                'manager': '',
                'expense_manager': '',
            }

    @http.route('/crm/user/save_profile', type='json', auth='user')
    def save_user_profile(self, name=None, login=None, email=None, phone=None, mobile=None):
        try:
            user = request.env.user.sudo()
            partner = user.partner_id.sudo() if user.partner_id else False
            user_vals = {}
            partner_vals = {}

            if login:
                cleaned_login = login.strip()
                if cleaned_login != user.login:
                    existing = request.env['res.users'].sudo().search([
                        ('login', '=ilike', cleaned_login),
                        ('id', '!=', user.id)
                    ], limit=1)
                    if existing:
                        return {'success': False, 'error': f"Login ID '{cleaned_login}' is already in use by another user."}
                    user_vals['login'] = cleaned_login

            if name:
                clean_name = name.strip()
                user_vals['name'] = clean_name
                if partner:
                    partner_vals['name'] = clean_name

            if email is not None:
                clean_email = email.strip()
                user_vals['email'] = clean_email
                if partner:
                    partner_vals['email'] = clean_email

            if phone is not None:
                clean_phone = phone.strip()
                if hasattr(user, 'phone'):
                    user_vals['phone'] = clean_phone
                if partner:
                    partner_vals['phone'] = clean_phone

            if mobile is not None:
                clean_mobile = mobile.strip()
                if hasattr(user, 'mobile'):
                    user_vals['mobile'] = clean_mobile
                if partner:
                    partner_vals['mobile'] = clean_mobile

            if user_vals:
                user.write(user_vals)
            if partner_vals and partner:
                partner.write(partner_vals)

            # Sync linked employee
            emp = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if emp:
                emp_vals = {}
                if name:
                    emp_vals['name'] = clean_name
                if email is not None:
                    emp_vals['work_email'] = clean_email
                if phone is not None:
                    emp_vals['work_phone'] = clean_phone
                if mobile is not None:
                    emp_vals['mobile_phone'] = clean_mobile
                if emp_vals:
                    emp.write(emp_vals)

            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

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
