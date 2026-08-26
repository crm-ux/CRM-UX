from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

class CrmWhitelabelController(http.Controller):
    
    @http.route(['/favicon.ico'], type='http', auth='public', website=True, multilang=False, sitemap=False, readonly=True)
    def favicon(self, **kw):
        return request.redirect('/web/static/img/favicon.ico', code=301)
    
class PersistentHome(Home):
    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        response = super(PersistentHome, self).web_login(redirect=redirect, **kw)
        if request and request.session and request.session.uid and response:
            # Set session_id cookie max-age to 90 days (7,776,000 seconds)
            response.set_cookie('session_id', request.session.sid, max_age=90 * 24 * 60 * 60, httponly=True)
        return response


