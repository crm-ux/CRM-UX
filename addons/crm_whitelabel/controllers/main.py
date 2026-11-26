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

    @http.route('/crm/user/get_profile', type='jsonrpc', auth='user')
    def get_user_profile(self, user_id=None, **kw):
        try:
            target_uid = int(user_id) if user_id else (int(kw.get('user_id')) if kw.get('user_id') else request.env.user.id)
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

            # 1. Job Position / Role
            job_title = ''
            if getattr(user, 'crm_job_id', None) and user.crm_job_id:
                job_title = user.crm_job_id.name or ''
            elif emp and getattr(emp, 'job_id', None) and emp.job_id:
                job_title = emp.job_id.name or ''
            elif emp and getattr(emp, 'job_title', None) and emp.job_title:
                job_title = emp.job_title or ''

            # 2. Department
            department = ''
            if getattr(user, 'crm_department_id', None) and user.crm_department_id:
                department = user.crm_department_id.name or ''
            elif emp and getattr(emp, 'department_id', None) and emp.department_id:
                department = emp.department_id.name or ''

            # 3. Reports To (Manager)
            manager = ''
            if getattr(user, 'crm_manager_id', None) and user.crm_manager_id:
                manager = user.crm_manager_id.name or ''
            elif emp and getattr(emp, 'parent_id', None) and emp.parent_id:
                manager = emp.parent_id.name or ''

            # 4. Expense / Voucher Approver
            expense_manager = ''
            try:
                approver = request.env['service.ticket'].sudo()._get_voucher_approver_for_employee(user)
                if approver:
                    expense_manager = approver.name or ''
            except Exception:
                pass
            if not expense_manager and getattr(user, 'crm_expense_manager_id', None) and user.crm_expense_manager_id:
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
            import logging
            _logger = logging.getLogger(__name__)
            _logger.exception("CRM profile load error: %s", e)
            u = request.env.user.sudo()
            return {
                'id': u.id,
                'name': u.name or '',
                'login': u.login or '',
                'email': u.email or (u.partner_id and u.partner_id.email) or '',
                'phone': getattr(u, 'phone', None) or (u.partner_id and u.partner_id.phone) or '',
                'mobile': getattr(u, 'mobile', None) or (u.partner_id and u.partner_id.mobile) or '',
                'image_128': False,
                'job_title': (getattr(u, 'crm_job_id', None) and u.crm_job_id.name) or '',
                'department': (getattr(u, 'crm_department_id', None) and u.crm_department_id.name) or '',
                'manager': (getattr(u, 'crm_manager_id', None) and u.crm_manager_id.name) or '',
                'expense_manager': (request.env['service.ticket'].sudo()._get_voucher_approver_for_employee(u).name if request.env['service.ticket'].sudo()._get_voucher_approver_for_employee(u) else (getattr(u, 'crm_expense_manager_id', None) and u.crm_expense_manager_id.name)) or '',
            }

    @http.route('/crm/user/save_profile', type='jsonrpc', auth='user')
    def save_user_profile(self, name=None, login=None, email=None, phone=None, mobile=None, **kw):
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

try:
    from odoo.addons.auth_signup.controllers.main import AuthSignupHome

    class CustomAuthSignupHome(AuthSignupHome):
        @http.route('/web/reset_password', type='http', auth='public', website=True, sitemap=False)
        def web_auth_reset_password(self, *args, **kw):
            qcontext = self.get_auth_signup_qcontext()
            if request.httprequest.method == 'POST' and (kw.get('login') or qcontext.get('login')):
                login_val = (kw.get('login') or qcontext.get('login') or '').strip()
                # Search by unique username (login) first, then fallback to email
                user = request.env['res.users'].sudo().search([('login', '=', login_val)], limit=1)
                if not user:
                    user = request.env['res.users'].sudo().search([('email', '=', login_val)], limit=1)
                
                if not user:
                    qcontext['error'] = "No user found with this username."
                    return request.render('auth_signup.reset_password', qcontext)
                
                user_email = user.email or (user.partner_id and user.partner_id.email)
                if not user_email or not user_email.strip():
                    qcontext['error'] = "No email address is linked to this account. Please contact your administrator to add your email."
                    return request.render('auth_signup.reset_password', qcontext)
                
                # Prepare partner signup token
                user.partner_id.action_signup_prepare()
                signup_urls = user.partner_id._get_signup_url_for_action()
                raw_url = signup_urls.get(user.partner_id.id, f"/web/reset_password?login={user.login}")

                # Ensure the reset URL includes the exact host and port (e.g. :8070)
                from urllib.parse import urlparse, urlunparse
                req_parsed = urlparse(request.httprequest.host_url)
                if raw_url.startswith('http://') or raw_url.startswith('https://'):
                    parsed = urlparse(raw_url)
                    reset_url = urlunparse((req_parsed.scheme, req_parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
                else:
                    base_url = request.httprequest.host_url.rstrip('/')
                    reset_url = f"{base_url}{raw_url}"

                # Test environment specific: If accessing via test IP, ensure port 8070 is attached
                if '34.14.132.247' in reset_url and ':8070' not in reset_url:
                    reset_url = reset_url.replace('34.14.132.247', '34.14.132.247:8070')

                # Compose professional branded email body
                company = user.company_id or request.env.company
                company_name = company.name or "YantraConnect CRM"
                
                body_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 30px; border: 1px solid #E2E8F0; border-radius: 12px; background: #FFFFFF;">
                    <div style="text-align: center; margin-bottom: 25px;">
                        <div style="width: 55px; height: 55px; background: #1a3d6e; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; color: white; font-size: 26px; font-weight: bold; line-height: 55px; margin-bottom: 10px;">Y</div>
                        <h2 style="color: #1a3d6e; margin: 0; font-size: 22px;">{company_name}</h2>
                        <p style="color: #64748B; font-size: 13px; margin: 4px 0 0 0;">Password Reset Request</p>
                    </div>
                    <p style="color: #1E293B; font-size: 14px; line-height: 1.6;">Hello <strong>{user.name}</strong>,</p>
                    <p style="color: #475569; font-size: 14px; line-height: 1.6;">A password reset was requested for your CRM account. Click the button below to choose your new password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" style="background: #1a3d6e; color: #FFFFFF; text-decoration: none; padding: 12px 30px; border-radius: 6px; font-weight: bold; font-size: 14px; display: inline-block;">Reset Password</a>
                    </div>
                    <p style="color: #64748B; font-size: 12px; line-height: 1.5;">If you did not request a password reset, you can safely ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 25px 0;"/>
                    <p style="color: #94A3B8; font-size: 11px; text-align: center; margin: 0;">&copy; {company_name}. All rights reserved.</p>
                </div>
                """
                
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart

                mail_server = request.env['ir.mail_server'].sudo().search([('active', '=', True)], limit=1)
                if not mail_server:
                    raise Exception("No active outgoing mail server configured in CRM.")

                host = mail_server.smtp_host or 'smtp.gmail.com'
                port = mail_server.smtp_port or 587
                user_smtp = mail_server.smtp_user or 'crm@yantradynamics.in'
                pass_smtp = (mail_server.smtp_pass or '').replace(' ', '')
                enc = mail_server.smtp_encryption or 'starttls'

                try:
                    # Use Odoo's native mail.mail model with the configured mail_server
                    email_from = f"{company_name} <{user_smtp}>"
                    mail_values = {
                        'subject': f"Password Reset Instructions - {company_name}",
                        'body_html': body_html,
                        'email_to': user_email,
                        'email_from': email_from,
                        'mail_server_id': mail_server.id,
                        'auto_delete': True,
                    }
                    mail = request.env['mail.mail'].sudo().create(mail_values)
                    mail.send(raise_exception=True)
                    qcontext['message'] = f"A password reset link has been sent to {user_email}. Please check your inbox or spam folder."
                    return request.render('auth_signup.reset_password', qcontext)
                except Exception as mail_err:
                    import sys
                    import traceback
                    import logging
                    _logger = logging.getLogger(__name__)

                    err_details = (
                        f"\n{'=' * 65}\n"
                        f"[RESET PASSWORD ERROR DETAILS]\n"
                        f"Recipient: {user_email}\n"
                        f"Mail Server ID: {mail_server.id} | Host: {host}:{port} | User: {user_smtp} | Enc: {enc}\n"
                        f"Error: {mail_err}\n"
                        f"Traceback:\n{traceback.format_exc()}\n"
                        f"{'=' * 65}\n"
                    )
                    # 1. Force flush to systemd console (stderr)
                    sys.stderr.write(err_details)
                    sys.stderr.flush()

                    # 2. Write directly to dedicated log file in /tmp
                    try:
                        with open('/tmp/crm_reset_password_error.log', 'w', encoding='utf-8') as f:
                            f.write(err_details)
                    except Exception:
                        pass

                    _logger.error("%s", err_details)
                    qcontext['dev_error_details'] = {
                        'recipient': user_email or '',
                        'host': host or '',
                        'port': str(port or ''),
                        'user': user_smtp or '',
                        'encryption': enc or '',
                        'odoo_error': str(mail_err or '').replace('"', "'"),
                        'smtp_error': str(mail_err or '').replace('"', "'"),
                    }
                    qcontext['error'] = "Unable to deliver the reset email due to a temporary service issue. Please try again after some time."
                    return request.render('auth_signup.reset_password', qcontext)

            return super(CustomAuthSignupHome, self).web_auth_reset_password(*args, **kw)
except Exception:
    pass
