from odoo import http
from odoo.http import request
odoo.addons.web.controllers.session import Session

class CrmWhitelabelController(http.Controller):
    
    @http.route(['/favicon.ico'], type='http', auth='public', website=True, multilang=False, sitemap=False, readonly=True)
    def favicon(self, **kw):
        return request.redirect('/web/static/img/favicon.ico', code=301)
    
class PersistentSession(Session):
    @http.route('/web/session/authenticate', type='json', auth="none")
    def authenticate(self, db, login, password, base_location=None):
        res = super(PersistentSession, self).authenticate(db, login, password, base_location)
        if request and request.session and request.session.sid:
            request.future_response.set_cookie(
                'session_id',
                request.session.sid,
                max_age=90 * 24 * 60 * 60,
                httponly=True
            )
        return res

