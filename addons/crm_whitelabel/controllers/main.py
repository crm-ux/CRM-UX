from odoo.addons.web.controllers.home import Home
from odoo import http
from odoo.http import request
import werkzeug

class LoginRedirect(Home):

    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        response = super().web_login(redirect=redirect, **kw)
        if request.session.uid:
            return werkzeug.utils.redirect('/odoo/action-435')
        return response

class WebsiteOverride(http.Controller):

    @http.route('/', type='http', auth='public', website=True, sitemap=False)
    def homepage(self, **kw):
        if request.session.uid:
            return werkzeug.utils.redirect('/odoo/action-435')
        return werkzeug.utils.redirect('/web/login')
