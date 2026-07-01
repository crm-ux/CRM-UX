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
        if not self.visiting_card:
            return
        try:
            import io
            import numpy as np
            import cv2
            from pyzbar import pyzbar
            import pytesseract
            from PIL import Image

            img_data = base64.b64decode(self.visiting_card)
            img = Image.open(io.BytesIO(img_data))
            parsed = {}

            # Step 1: QR code scan first
            img_cv = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
            qr_codes = pyzbar.decode(img_cv)
            if qr_codes:
                qr_text = qr_codes[0].data.decode('utf-8', errors='ignore')
                _logger.warning("QR found: %s", qr_text)
                parsed = self._parse_qr_data(qr_text)

            # Step 2: OCR - always run to supplement QR
            ocr_text = pytesseract.image_to_string(img)
            _logger.warning("OCR text: %s", ocr_text)
            ocr = self._parse_card_text(ocr_text)

            # Merge: QR priority, OCR fills gaps
            for k in ['name', 'company', 'designation', 'address', 'city', 'website']:
                if not parsed.get(k):
                    parsed[k] = ocr.get(k, '')
            if not parsed.get('phones'):
                parsed['phones'] = ocr.get('phones', [])
            if not parsed.get('emails'):
                parsed['emails'] = ocr.get('emails', [])

            # Set fields
            if parsed.get('name'):
                self.contact_name = parsed['name']
            if parsed.get('company'):
                self.company_name = parsed['company']
            if parsed.get('designation'):
                self.designation = parsed['designation']
            if parsed.get('address'):
                self.address = parsed['address']
            if parsed.get('city'):
                self.city = parsed['city']
            if parsed.get('website'):
                self.website = parsed['website']

            self.phone_ids = [(5, 0, 0)]
            for phone in parsed.get('phones', []):
                self.phone_ids = [(0, 0, {'phone': phone, 'phone_type': 'mobile'})]

            self.email_ids = [(5, 0, 0)]
            for email in parsed.get('emails', []):
                self.email_ids = [(0, 0, {'email': email, 'email_type': 'work'})]

        except Exception as e:
            _logger.warning("Auto scan failed: %s", str(e))

    def _parse_qr_data(self, qr_text):
        result = {'phones': [], 'emails': []}
        if not qr_text:
            return result
        if 'BEGIN:VCARD' in qr_text.upper():
            for line in qr_text.split('\n'):
                line = line.strip()
                ul = line.upper()
                if ul.startswith('FN:'):
                    result['name'] = line[3:].strip()
                elif ul.startswith('ORG:'):
                    result['company'] = line[4:].strip()
                elif ul.startswith('TITLE:'):
                    result['designation'] = line[6:].strip()
                elif 'TEL' in ul and ':' in line:
                    phone = line.split(':')[-1].strip()
                    digits = re.sub(r'[^\d]', '', phone)
                    if digits.startswith('91') and len(digits) == 12:
                        digits = digits[2:]
                    if len(digits) >= 10:
                        result['phones'].append(digits[-10:])
                elif 'EMAIL' in ul and ':' in line:
                    email = line.split(':')[-1].strip()
                    if '@' in email:
                        result['emails'].append(email)
                elif ul.startswith('URL:'):
                    result['website'] = line[4:].strip()
                elif ul.startswith('ADR:'):
                    result['address'] = line[4:].replace(';', ' ').strip()
        else:
            result = self._parse_card_text(qr_text)
        return result

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

    @api.constrains('contact_name', 'company_name')
    def _check_duplicate_contact(self):
        for rec in self:
            if rec.contact_name and rec.company_name:
                duplicate = self.search([
                    ('contact_name', '=ilike', rec.contact_name),
                    ('company_name', '=ilike', rec.company_name),
                    ('id', '!=', rec.id),
                ], limit=1)
                if duplicate:
                    raise UserError(
                        _('Contact "%s" from company "%s" already exists. Duplicate entry not allowed.') % (rec.contact_name, rec.company_name)
                    )
            elif rec.contact_name:
                duplicate = self.search([
                    ('contact_name', '=ilike', rec.contact_name),
                    ('id', '!=', rec.id),
                ], limit=1)
                if duplicate:
                    raise UserError(
                        _('Contact "%s" already exists. Duplicate entry not allowed.') % rec.contact_name
                    )

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

        # 1. Emails - most reliable
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        result['emails'] = list(set(emails))

        # 2. Phones - flexible pattern for all formats
        cleaned_phones = []
        seen_phones = set()
        # Match any number-like sequence with optional +, spaces, dashes, brackets
        phone_pattern = re.findall(r'[\+]?[\d][\d\s\-\.\(\)]{7,}[\d]', text)
        for p in phone_pattern:
            digits = re.sub(r'[^\d]', '', p)
            # Remove leading country codes
            if digits.startswith('0091'):
                digits = digits[4:]
            elif digits.startswith('91') and len(digits) == 12:
                digits = digits[2:]
            elif digits.startswith('0') and len(digits) == 11:
                digits = digits[1:]
            # Accept 7-15 digit numbers
            if 7 <= len(digits) <= 15 and digits not in seen_phones:
                seen_phones.add(digits)
                cleaned_phones.append(digits)
        result['phones'] = cleaned_phones[:5]

        # 3. Website
        websites = re.findall(r'(?:www\.[\w.-]+|https?://[\w./-]+)', text, re.IGNORECASE)
        if websites:
            result['website'] = websites[0].rstrip('.,')

        # 4. Company name - has business keywords
        company_keywords = ['pvt', 'ltd', 'llp', 'inc', 'corp', 'technologies', 'technology',
                           'solutions', 'services', 'industries', 'enterprises', 'group',
                           'international', 'systems', 'consultancy', 'trading', 'exports',
                           'imports', 'manufacturing', 'pharma', 'chemicals', 'labs',
                           'laboratory', 'associates', 'co.', '& co', 'company']
        for line in lines:
            if any(k in line.lower() for k in company_keywords) and len(line) > 3:
                result['company'] = line
                break

        # 5. Designation - has job keywords
        designation_keywords = ['director', 'manager', 'ceo', 'cto', 'cfo', 'engineer',
                               'executive', 'officer', 'president', 'founder', 'partner',
                               'consultant', 'analyst', 'developer', 'designer', 'head',
                               'lead', 'senior', 'junior', 'associate', 'assistant',
                               'proprietor', 'owner', 'md', 'gm', 'vp', 'avp',
                               'sales', 'marketing', 'accounts', 'purchase', 'hr', 'admin']
        for line in lines:
            if any(k in line.lower() for k in designation_keywords) and len(line) < 60:
                result['designation'] = line
                break

        # 6. Person name - short, title case, not company/designation/email/phone
        skip_lines = {result.get('company', ''), result.get('designation', '')}
        name_prefixes = ['mr', 'mrs', 'ms', 'dr', 'prof', 'er', 'ca', 'cs', 'adv', 'shri']
        for line in lines:
            if line in skip_lines or not line:
                continue
            if '@' in line or re.search(r'\d', line):
                continue
            if len(line) < 3 or len(line) > 50:
                continue
            words = line.split()
            if len(words) < 1 or len(words) > 5:
                continue
            first_word = words[0].lower().rstrip('.')
            if first_word in name_prefixes:
                result['name'] = line
                break
            if all(w[0].isupper() for w in words if len(w) > 1):
                if not any(k in line.lower() for k in company_keywords + designation_keywords):
                    result['name'] = line
                    break

        # 7. Address lines
        address_keywords = ['street', 'road', 'nagar', 'floor', 'sector', 'plot', 'area',
                           'near', 'opp', 'dist', 'pin', 'phase', 'block', 'colony',
                           'industrial', 'estate', 'building', 'tower', 'complex', 'survey',
                           'shop', 'office', 'unit', 'flat', 'apartment', 'lane', 'taluka',
                           'chowk', 'bazaar', 'market', 'circle', 'cross', 'main', 'village']
        skip_addr = {result.get('company',''), result.get('designation',''), result.get('name','')}
        addr_lines = []
        for line in lines:
            if line in skip_addr or not line:
                continue
            if '@' in line or re.search(r'\d{10}', line):
                continue
            line_lower = line.lower()
            if any(k in line_lower for k in address_keywords) or re.search(r'\b\d{6}\b', line):
                addr_lines.append(line)
        if addr_lines:
            result['address'] = '\n'.join(addr_lines[:5])

        # 8. City from pincode
        for line in lines:
            pincode = re.search(r'\b(\d{6})\b', line)
            if pincode:
                city = re.sub(r'\d{6}', '', line).strip().strip('-, ')
                if city and len(city) > 2:
                    result['city'] = city
                break

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
