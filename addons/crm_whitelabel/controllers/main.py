from odoo import http
from odoo.http import request, root, SessionExpiredException
from odoo.addons.web.controllers.home import Home

# 90 Days in Seconds
SESSION_90_DAYS = 90 * 24 * 60 * 60

# Override Server-side Session Lifetime on Disk
if hasattr(root, 'session_store'):
    root.session_store.session_timeout = SESSION_90_DAYS

# Patch FutureResponse.set_cookie to enforce 90 days on all session_id cookies
orig_set_cookie = http.FutureResponse.set_cookie

def persistent_set_cookie(self, key, value='', max_age=None, expires=None, path='/', domain=None, secure=False, httponly=False, samesite=None, cookie_type='required'):
    if key == 'session_id':
        max_age = SESSION_90_DAYS
        expires = None
    return orig_set_cookie(self, key, value=value, max_age=max_age, expires=expires, path=path, domain=domain, secure=secure, httponly=httponly, samesite=samesite, cookie_type=cookie_type)

http.FutureResponse.set_cookie = persistent_set_cookie

class CrmWhitelabelController(http.Controller):
    
    @http.route(['/favicon.ico'], type='http', auth='public', website=True, multilang=False, sitemap=False, readonly=True)
    def favicon(self, **kw):
        return request.redirect('/web/static/img/favicon.ico', code=301)
    
class PersistentHome(Home):
    @http.route('/', type='http', auth="none")
    def index(self, s_action=None, **kw):
        if request.session.uid:
            return request.redirect('/app/action-435')
        return super(PersistentHome, self).index(s_action=s_action, **kw)

    @http.route('/web/login', type='http', auth="public", sitemap=False)
    def web_login(self, redirect=None, **kw):
        # If user is ALREADY logged in, send them straight to Dashboard
        if request.session.uid and not redirect:
            return request.redirect('/app/action-435')
        
        response = super(PersistentHome, self).web_login(redirect=redirect, **kw)
        
        # Enforce 90 days on login response
        if request and request.session and request.session.uid and response:
            response.set_cookie('session_id', request.session.sid, max_age=SESSION_90_DAYS, httponly=True)
            
        return response
