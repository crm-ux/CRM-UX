from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import re
import logging

_logger = logging.getLogger(__name__)


class ExhibitionContactPhone(models.Model):
    _name = 'exhibition.contact.phone'
    _description = 'Exhibition Contact Phone'

    contact_id = fields.Many2one('exhibition.contact', string='Contact', ondelete='cascade')
    phone = fields.Char(string='Mobile / Phone', required=True)
    phone_type = fields.Selection([
        ('mobile', 'Mobile'),
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp'),
    ], string='Type', default='mobile')


class ExhibitionContactEmail(models.Model):
    _name = 'exhibition.contact.email'
    _description = 'Exhibition Contact Email'

    contact_id = fields.Many2one('exhibition.contact', string='Contact', ondelete='cascade')
    email = fields.Char(string='Email', required=True)
    email_type = fields.Selection([
        ('work', 'Work'),
        ('personal', 'Personal'),
    ], string='Type', default='work')


class ExhibitionContact(models.Model):
    _name = 'exhibition.contact'
    _description = 'Exhibition Contact'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'contact_name'

    contact_name = fields.Char(string='Contact Person', required=True, tracking=True)
    company_name = fields.Char(string='Company Name', tracking=True)
    designation = fields.Char(string='Designation')
    website = fields.Char(string='Website')
    address = fields.Text(string='Address')
    city = fields.Char(string='City')
    x_state = fields.Char(string='State')
    country = fields.Char(string='Country')
    notes = fields.Text(string='Notes')
    exhibition_name = fields.Char(string='Exhibition / Event Name')
    exhibition_date = fields.Date(string='Exhibition Date', default=fields.Date.today)
    phone_ids = fields.One2many('exhibition.contact.phone', 'contact_id', string='Phone Numbers')
    email_ids = fields.One2many('exhibition.contact.email', 'contact_id', string='Email Addresses')
    visiting_card = fields.Binary(string='Visiting Card / Photo')
    visiting_card_filename = fields.Char(string='Filename')
    crm_lead_id = fields.Many2one('crm.lead', string='Linked CRM Lead', readonly=True)
    x_status = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('converted', 'Converted'),
    ], string='Status', default='new', tracking=True)

    @api.onchange('visiting_card')
    def _onchange_visiting_card(self):
        if self.visiting_card:
            try:
                import pytesseract
                from PIL import Image
                import io
                img_data = base64.b64decode(self.visiting_card)
                img = Image.open(io.BytesIO(img_data))
                text = pytesseract.image_to_string(img)
                parsed = self._parse_card_text(text)
                # Clear and refill all fields on re-upload
                self.contact_name = parsed.get('name', '') or self.contact_name
                self.company_name = parsed.get('company', '') or self.company_name
                self.designation = parsed.get('designation', '') or self.designation
                self.address = parsed.get('address', '') or self.address
                self.website = parsed.get('website', '') or self.website
                # Reset and refill phones
                self.phone_ids = [(5, 0, 0)]
                for phone in parsed.get('phones', []):
                    self.phone_ids = [(0, 0, {'phone': phone, 'phone_type': 'mobile'})]
                # Reset and refill emails
                self.email_ids = [(5, 0, 0)]
                for email in parsed.get('emails', []):
                    self.email_ids = [(0, 0, {'email': email, 'email_type': 'work'})]
            except Exception as e:
                _logger.warning("Auto scan failed: %s", str(e))

    @api.onchange('company_name')
    def _onchange_company_name(self):
        if self.company_name:
            duplicates = self.search([
                ('company_name', '=ilike', self.company_name),
                ('id', '!=', self._origin.id if self._origin else False),
            ])
            if duplicates:
                return {
                    'warning': {
                        'title': 'Duplicate Company Found!',
                        'message': 'Company "%s" already exists with %d contact(s). Please check before saving.' % (self.company_name, len(duplicates)),
                    }
                }

    def action_scan_card(self):
        self.ensure_one()
        if not self.visiting_card:
            raise UserError(_('Please upload a visiting card image first.'))
        try:
            import pytesseract
            from PIL import Image
            import io
            img_data = base64.b64decode(self.visiting_card)
            img = Image.open(io.BytesIO(img_data))
            text = pytesseract.image_to_string(img)
            parsed = self._parse_card_text(text)
            if parsed.get('name') and not self.contact_name:
                self.contact_name = parsed['name']
            if parsed.get('company') and not self.company_name:
                self.company_name = parsed['company']
            if parsed.get('designation') and not self.designation:
                self.designation = parsed['designation']
            if parsed.get('address') and not self.address:
                self.address = parsed['address']
            if parsed.get('website') and not self.website:
                self.website = parsed['website']
            for phone in parsed.get('phones', []):
                if phone not in self.phone_ids.mapped('phone'):
                    self.phone_ids = [(0, 0, {'phone': phone, 'phone_type': 'mobile'})]
            for email in parsed.get('emails', []):
                if email not in self.email_ids.mapped('email'):
                    self.email_ids = [(0, 0, {'email': email, 'email_type': 'work'})]
            return True
        except ImportError:
            raise UserError(_('Tesseract OCR is not installed. Please install pytesseract and tesseract-ocr.'))
        except Exception as e:
            raise UserError(_('Error scanning card: %s') % str(e))

    def _parse_card_text(self, text):
        result = {'phones': [], 'emails': []}
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # Extract emails
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        result['emails'] = list(set(emails))
        # Extract phones - find each number separately per line
        cleaned_phones = []
        seen = set()
        for line in text.split('\n'):
            line = line.strip()
            # Find all phone-like patterns in this line
            line_phones = re.findall(r'(?:\+91[\s\-]?)?[6-9]\d{9}|(?:\+\d{1,3}[\s\-]?)?\d{10}', line)
            for p in line_phones:
                digits = re.sub(r'[^\d]', '', p)
                if len(digits) == 10:
                    # Indian mobile - store as-is without country code
                    formatted = digits
                elif len(digits) == 12 and digits.startswith('91'):
                    # +91 prefix - remove country code
                    formatted = digits[2:]
                elif len(digits) >= 10:
                    formatted = digits
                else:
                    continue
                if formatted not in seen and len(formatted) >= 10:
                    seen.add(formatted)
                    cleaned_phones.append(formatted)
        result['phones'] = cleaned_phones[:5]
        # Extract website
        websites = re.findall(r'(?:www\.|https?://)[^\s]+', text, re.IGNORECASE)
        if websites:
            result['website'] = websites[0]
        # First non-email, non-phone line is likely the name
        for line in lines:
            if not re.search(r'[@\d+]', line) and len(line.split()) <= 4 and len(line) > 3:
                result['name'] = line
                break
        # Address lines
        address_keywords = ['street', 'road', 'nagar', 'floor', 'sector', 'plot', 'area', 'near', 'opp', 'dist']
        addr_lines = [l for l in lines if any(k in l.lower() for k in address_keywords)]
        if addr_lines:
            result['address'] = '\n'.join(addr_lines)
        return result

    def action_convert_to_lead(self):
        self.ensure_one()
        if self.crm_lead_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'crm.lead',
                'res_id': self.crm_lead_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        phone = self.phone_ids[0].phone if self.phone_ids else ''
        email = self.email_ids[0].email if self.email_ids else ''
        lead = self.env['crm.lead'].create({
            'name': self.company_name or self.contact_name,
            'contact_name': self.contact_name,
            'partner_name': self.company_name,
            'phone': phone,
            'email_from': email,
            'street': self.address,
            'city': self.city,
            'description': self.notes or '',
        })
        self.crm_lead_id = lead.id
        self.x_status = 'converted'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_check_duplicate(self):
        self.ensure_one()
        if not self.company_name:
            return
        duplicates = self.search([
            ('company_name', '=ilike', self.company_name),
            ('id', '!=', self.id),
        ])
        if duplicates:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Possible Duplicates: %s') % self.company_name,
                'res_model': 'exhibition.contact',
                'view_mode': 'list,form',
                'domain': [('id', 'in', duplicates.ids)],
                'target': 'new',
            }
