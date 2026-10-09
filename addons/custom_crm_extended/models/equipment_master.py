from lxml import etree
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class EquipmentCategory(models.Model):
    _name = 'equipment.category'
    _description = 'Equipment Category'

    name = fields.Char(string='Category Name', required=True)

class EquipmentMaster(models.Model):
    _name = 'equipment.master'
    _description = 'Equipment Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        ('equipment_id_uniq', 'unique(equipment_id)', 'The Equipment ID must be unique! This ID is already assigned to another equipment.'),
        ('serial_number_uniq', 'unique(serial_number)', 'The Serial Number must be unique! This Serial Number already exists in the system.'),
    ]

    # Step 1: Equipment Info
    equipment_id  = fields.Char(string='Equipment ID', required=True, tracking=True, readonly=True)
    name = fields.Many2one('product.template', string='Model Name', tracking=True)
    category_id = fields.Char(string='Equipment', tracking=True)
    manufacturer = fields.Char(string='Manufacturer', tracking=True)
    model_number = fields.Char(string='Equipment Owner', tracking=True)
    serial_number = fields.Char(string='Serial Number', tracking=True)
    part_number = fields.Char(string='Part Number', tracking=True)
    child_part_no = fields.Char(string='Child Part No', tracking=True)
    invoice_number = fields.Char(string='Invoice No', tracking=True)
    invoice_attachment = fields.Binary(string='Invoice Attachment')
    invoice_filename = fields.Char(string='Invoice Filename')
    invoice_date = fields.Date(string='Invoice Date', tracking=True)

    SUPPORTED_EXTENSIONS = (
        'pdf',
        'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'svg',
        'docx', 'doc',
        'xlsx', 'xls', 'csv',
        'txt',
        'zip', 'rar', '7z', 'tar', 'gz'
    )

    @api.constrains('invoice_attachment', 'invoice_filename')
    def _check_invoice_file_format(self):
        for rec in self:
            if rec.invoice_attachment and rec.invoice_filename:
                fn = rec.invoice_filename.strip().lower()
                ext = fn.split('.')[-1] if '.' in fn else ''
                if ext in ('exe', 'bat', 'cmd', 'sh', 'bin', 'msi', 'com', 'scr', 'vbs', 'js', 'py'):
                    raise ValidationError(_(
                        "Executable files (.%s) are strictly prohibited for security reasons!\n"
                        "Please upload a supported document (PDF, Images, DOCX, XLSX, TXT, ZIP)."
                    ) % ext)
                if ext not in self.SUPPORTED_EXTENSIONS:
                    raise ValidationError(_(
                        "The file format '%s' is not supported!\n"
                        "Supported formats are: PDF, Images (PNG, JPG, WEBP, SVG), Word (DOCX), Excel (XLSX, CSV), Text (TXT), and Archives (ZIP, RAR)."
                    ) % (ext.upper() if ext else 'Unknown'))

    def action_preview_invoice(self):
        """Action button method for form view (UI preview intercepted in JS)."""
        return True

    @api.model
    def action_get_invoice_preview_content(self, res_id=None, raw_b64=None, filename=None):
        """Extract previewable content for DOCX (text/HTML) or ZIP (list of files)."""
        import base64
        import io
        import zipfile
        import xml.etree.ElementTree as ET

        attachment_b64 = raw_b64
        fname = filename or ''

        if res_id:
            rec = self.browse(res_id)
            if rec.exists():
                attachment_b64 = attachment_b64 or rec.invoice_attachment
                fname = fname or rec.invoice_filename or ''
        elif self and len(self) == 1:
            attachment_b64 = attachment_b64 or self.invoice_attachment
            fname = fname or self.invoice_filename or ''

        if not attachment_b64:
            return {'type': 'empty'}

        try:
            raw_bytes = base64.b64decode(attachment_b64)
            ext = fname.lower().split('.')[-1] if '.' in fname else ''

            # 1. Parse ZIP archive: return clean list of files with sizes
            if ext in ('zip', 'rar', '7z', 'tar', 'gz'):
                file_list = []
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                    for info in z.infolist():
                        file_list.append({
                            'name': info.filename,
                            'size': round(info.file_size / 1024, 1),
                            'is_dir': info.is_dir(),
                        })
                return {
                    'type': 'zip_content',
                    'filename': fname,
                    'files': file_list,
                    'total_count': len(file_list),
                }

            # 2. Parse Word Document (.docx is a ZIP containing word/document.xml)
            elif ext in ('docx', 'doc'):
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                    if 'word/document.xml' not in z.namelist():
                        return {'type': 'docx_content', 'filename': fname, 'html': '<p class="text-muted">Empty document.</p>'}

                    xml_content = z.read('word/document.xml')
                    tree = ET.fromstring(xml_content)

                    # Extract embedded images and map r:id -> base64 data URI
                    media_map = {}
                    if 'word/_rels/document.xml.rels' in z.namelist():
                        try:
                            rels_xml = z.read('word/_rels/document.xml.rels')
                            rels_tree = ET.fromstring(rels_xml)
                            for rel in rels_tree:
                                r_id = rel.get('Id')
                                target = rel.get('Target', '')
                                if 'media/' in target:
                                    img_path = 'word/' + target.lstrip('/')
                                    if img_path in z.namelist():
                                        img_bytes = z.read(img_path)
                                        img_ext = img_path.split('.')[-1].lower()
                                        mime = 'image/jpeg' if img_ext in ('jpg', 'jpeg') else f'image/{img_ext}'
                                        media_map[r_id] = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
                        except Exception:
                            pass

                    # Parse elements in document body preserving order of tables, paragraphs, and images
                    ns = {
                        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
                    }

                    body = tree.find('.//w:body', ns)
                    html_parts = []

                    def extract_p_html(p_elem):
                        p_html = []
                        # Look for drawings/images in this paragraph
                        for blip in p_elem.iterfind('.//a:blip', ns):
                            embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                            if embed_id and embed_id in media_map:
                                p_html.append(f'<div class="my-2 text-center"><img src="{media_map[embed_id]}" class="img-fluid rounded shadow-sm" style="max-height: 280px; max-width: 100%; object-fit: contain;" /></div>')

                        # Text runs
                        runs_text = []
                        for r_node in p_elem.iterfind('.//w:r', ns):
                            r_is_bold = r_node.find('.//w:b', ns) is not None
                            t_nodes = [t.text for t in r_node.iterfind('.//w:t', ns) if t.text]
                            if t_nodes:
                                text_val = ''.join(t_nodes).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                if r_is_bold:
                                    runs_text.append(f"<strong>{text_val}</strong>")
                                else:
                                    runs_text.append(text_val)

                        if runs_text:
                            p_html.append(''.join(runs_text))

                        return ''.join(p_html)

                    if body is not None:
                        for child in body:
                            tag = child.tag.split('}')[-1]
                            if tag == 'p':
                                inner = extract_p_html(child)
                                if inner.strip():
                                    html_parts.append(f'<p class="mb-2" style="line-height: 1.5;">{inner}</p>')
                            elif tag == 'tbl':
                                # Dynamic HTML table generated directly from Word XML properties
                                rows_html = []
                                for tr in child.iterfind('.//w:tr', ns):
                                    cells_html = []
                                    for tc in tr.iterfind('.//w:tc', ns):
                                        tcPr = tc.find('.//w:tcPr', ns)
                                        # 1. Dynamic Colspan (w:gridSpan)
                                        colspan_attr = ''
                                        if tcPr is not None:
                                            grid_span = tcPr.find('.//w:gridSpan', ns)
                                            if grid_span is not None:
                                                span_val = grid_span.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                                                if span_val and span_val.isdigit() and int(span_val) > 1:
                                                    colspan_attr = f' colspan="{span_val}"'

                                        # 2. Dynamic Cell Shading / Background (w:shd)
                                        cell_bg = ''
                                        if tcPr is not None:
                                            shd = tcPr.find('.//w:shd', ns)
                                            if shd is not None:
                                                fill = shd.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill', '')
                                                if fill and fill != 'auto' and fill != 'FFFFFF':
                                                    cell_bg = f'background-color: #{fill} !important;'

                                        # 3. Dynamic Text Content & Paragraph Alignment
                                        cell_paragraphs = []
                                        cell_align = 'left'
                                        for p in tc.iterfind('.//w:p', ns):
                                            p_jc = p.find('.//w:jc', ns)
                                            if p_jc is not None:
                                                val = p_jc.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
                                                if val in ('center', 'right', 'left'):
                                                    cell_align = val
                                            p_text = extract_p_html(p)
                                            if p_text:
                                                cell_paragraphs.append(p_text)
                                        cell_content = '<br/>'.join(cell_paragraphs) if cell_paragraphs else '&nbsp;'

                                        # Inline style built directly from Word file properties
                                        td_style = f'border: 1px solid #000; padding: 6px 10px; vertical-align: middle; text-align: {cell_align}; {cell_bg}'
                                        cells_html.append(f'<td{colspan_attr} style="{td_style}">{cell_content}</td>')

                                    if cells_html:
                                        rows_html.append(f'<tr>{"".join(cells_html)}</tr>')

                                if rows_html:
                                    html_parts.append(f'<div class="my-3" style="width: 100%; overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; border: 1.5px solid #000; font-size: 13.5px; table-layout: auto;"><tbody>{"".join(rows_html)}</tbody></table></div>')

                    rendered_html = ''.join(html_parts) if html_parts else '<p class="text-muted">No readable content found in document.</p>'
                    return {
                        'type': 'docx_content',
                        'filename': fname,
                        'html': rendered_html,
                    }

            # 3. Parse Excel / Spreadsheet (.xlsx, .xls, .csv)
            elif ext in ('xlsx', 'xls', 'csv'):
                sheets_data = []

                if ext == 'csv':
                    import csv
                    try:
                        text_data = raw_bytes.decode('utf-8-sig', errors='replace')
                    except Exception:
                        text_data = raw_bytes.decode('latin-1', errors='replace')
                    reader = csv.reader(io.StringIO(text_data))
                    rows = [row for row in reader if any(cell.strip() for cell in row)]
                    sheets_data.append({
                        'name': 'CSV Data',
                        'rows': rows[:250], # preview up to 250 rows
                    })
                elif ext == 'xlsx':
                    # Parse xlsx directly using openpyxl or XML parsing from zip container
                    try:
                        import openpyxl
                        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True, read_only=True)
                        for sheetname in wb.sheetnames:
                            sheet = wb[sheetname]
                            sheet_rows = []
                            for row in sheet.iter_rows(values_only=True):
                                if any(val is not None and str(val).strip() != '' for val in row):
                                    sheet_rows.append([str(val) if val is not None else '' for val in row])
                                if len(sheet_rows) >= 250:
                                    break
                            if sheet_rows:
                                sheets_data.append({
                                    'name': sheetname,
                                    'rows': sheet_rows,
                                })
                    except Exception:
                        # Fallback using zipfile to parse sheet1.xml if openpyxl not installed
                        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                            # Read shared strings if present
                            shared_strings = []
                            if 'xl/sharedStrings.xml' in z.namelist():
                                sst_tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                                ns_s = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                                for si in sst_tree.findall('.//x:si', ns_s):
                                    t = si.find('.//x:t', ns_s)
                                    shared_strings.append(t.text if t is not None and t.text else '')

                            for name in z.namelist():
                                if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
                                    sheet_tree = ET.fromstring(z.read(name))
                                    ns_x = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                                    parsed_rows = []
                                    for r in sheet_tree.findall('.//x:row', ns_x):
                                        row_vals = []
                                        for c in r.findall('.//x:c', ns_x):
                                            c_type = c.get('t')
                                            v = c.find('.//x:v', ns_x)
                                            val_str = ''
                                            if v is not None and v.text:
                                                if c_type == 's' and v.text.isdigit():
                                                    idx = int(v.text)
                                                    val_str = shared_strings[idx] if idx < len(shared_strings) else v.text
                                                else:
                                                    val_str = v.text
                                            row_vals.append(val_str)
                                        if any(row_vals):
                                            parsed_rows.append(row_vals)
                                        if len(parsed_rows) >= 250:
                                            break
                                    if parsed_rows:
                                        sheets_data.append({
                                            'name': f'Sheet {len(sheets_data) + 1}',
                                            'rows': parsed_rows,
                                        })
                elif ext == 'xls':
                    # Parse legacy Excel using xlrd
                    try:
                        import xlrd
                        wb = xlrd.open_workbook(file_contents=raw_bytes)
                        for sheet in wb.sheets():
                            sheet_rows = []
                            for r in range(min(sheet.nrows, 250)):
                                row_vals = [str(val) for val in sheet.row_values(r)]
                                if any(v.strip() for v in row_vals):
                                    sheet_rows.append(row_vals)
                            if sheet_rows:
                                sheets_data.append({
                                    'name': sheet.name,
                                    'rows': sheet_rows,
                                })
                    except Exception:
                        pass

                return {
                    'type': 'excel_content',
                    'filename': fname,
                    'sheets': sheets_data,
                }
        except Exception as e:
            return {'type': 'error', 'error': str(e)}

        return {'type': 'unsupported'}
    equipment_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('under_repair', 'Under Repair'),
    ], string='Equipment Status', default='active', tracking=True)
    criticality = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Criticality', default='medium', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)
    user_id = fields.Many2one('res.users', string='Assigned Responsible', default=lambda self: self.env.user, tracking=True)

    # Step 2: Location & Contact
    partner_id = fields.Many2one('res.partner', string='Customer Name', tracking=True)
    site_name = fields.Char(string='Site Name', tracking=True)
    building = fields.Char(string='Building', tracking=True)
    floor = fields.Char(string='Floor', tracking=True)
    department = fields.Char(string='Department', tracking=True)
    room_number = fields.Char(string='Room Number', tracking=True)
    address = fields.Text(string='Address')
    contact_person = fields.Char(string='Contact Person', tracking=True)
    contact_number = fields.Char(string='Contact Number', tracking=True)
    email = fields.Char(string='Email', tracking=True)

    # Step 3: Maintenance & Contract
    installation_date = fields.Date(string='Installation Date')
    warranty_start_date = fields.Date(string='Warranty Start Date')
    warranty_end_date = fields.Date(string='Warranty End Date')
    service_contract = fields.Selection([
        ('amc', 'AMC'),
        ('cmc', 'CMC'),
        ('warranty', 'Warranty'),
        ('none', 'None'),
    ], string='Service Contract', default='amc', tracking=True)
    last_preventive_maintenance = fields.Date(string='Last PM Date')
    next_preventive_maintenance = fields.Date(string='Next PM Date')
    last_breakdown_date = fields.Date(string='Last Breakdown Date')
    calibration_due_date = fields.Date(string='Calibration Due Date')
    running_status = fields.Selection([
        ('running', 'Running'),
        ('stopped', 'Stopped'),
    ], string='Current Running Status', default='running', tracking=True)

    # Step 4: Specs & Remarks
    firmware_version = fields.Char(string='Software/Firmware Version')
    accessories = fields.Text(string='Accessories')
    remarks = fields.Text(string='Remarks')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            p = self.partner_id
            contact_name = ""
            contact_phone = ""
            contact_email = ""

            def get_phone(partner):
                if not partner:
                    return ""
                return getattr(partner, 'mobile', False) or getattr(partner, 'phone', False) or ""

            if p.is_company:
                primary_contact = p.child_ids.filtered(lambda c: c.type == 'contact')[:1]
                if primary_contact:
                    c = primary_contact[0]
                    contact_name = c.name or p.name or ""
                    contact_phone = get_phone(c) or get_phone(p)
                    contact_email = c.email or p.email or ""
                else:
                    contact_name = p.name or ""
                    contact_phone = get_phone(p)
                    contact_email = p.email or ""
            else:
                contact_name = p.name or ""
                contact_phone = get_phone(p) or get_phone(p.parent_id)
                contact_email = p.email or (p.parent_id.email if p.parent_id else False) or ""

            self.contact_person = contact_name
            self.contact_number = contact_phone
            self.email = contact_email

            # Format Address (Restored!)
            addr_parts = [p.street, p.street2, p.city, p.state_id.name if p.state_id else False, p.country_id.name if p.country_id else False, p.zip]
            self.address = ", ".join([str(a) for a in addr_parts if a])

            # Auto-fill location fields
            self.site_name = getattr(p, 'x_site_name', False) or (getattr(p.parent_id, 'x_site_name', False) if p.parent_id else "") or ""
            self.building = getattr(p, 'x_building', False) or ""
            self.floor = getattr(p, 'x_floor', False) or ""
            self.department = getattr(p, 'x_department', False) or p.function or ""
            self.room_number = getattr(p, 'x_room_number', False) or ""

    @api.depends('name', 'serial_number', 'equipment_id')
    def _compute_display_name(self):
        for rec in self:
            eq_name = rec.name.display_name if rec.name else (rec.equipment_id or '')
            if rec.serial_number:
                sn = str(rec.serial_number).strip()
                last6 = sn[-6:] if len(sn) >= 6 else sn
                rec.display_name = f"{eq_name} ...{last6}"
            else:
                rec.display_name = eq_name

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = list(domain or [])
        if name:
            domain += ['|', '|', ('name.name', operator, name), ('serial_number', operator, name), ('equipment_id', operator, name)]
        records = self.search(domain, limit=limit)
        return [(r.id, r.display_name) for r in records]

    @api.constrains('equipment_id')
    def _check_unique_equipment_id(self):
        for rec in self:
            if rec.equipment_id:
                duplicate = self.search([
                    ('equipment_id', '=', rec.equipment_id.strip()),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("Equipment ID '%s' already exists! Please use a unique Equipment ID.") % rec.equipment_id)

    @api.constrains('serial_number')
    def _check_unique_serial_number(self):
        for rec in self:
            if rec.serial_number and rec.serial_number.strip():
                duplicate = self.search([
                    ('serial_number', '=', rec.serial_number.strip()),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("Serial Number '%s' already exists! Each equipment must have a unique Serial Number.") % rec.serial_number)

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.category_id = self.name.categ_id.display_name if self.name.categ_id else ''
            self.manufacturer = getattr(self.name, 'x_make', '') or ''
            self.part_number = getattr(self.name, 'default_code', '') or ''
        else:
            self.category_id = ''
            self.manufacturer = ''
            self.part_number = ''

    def action_create_service_ticket(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Service Ticket'),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': f"Service Ticket - {self.name.name if self.name else ''}",
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            }
        }

    @api.model
    def _user_can(self, perm_name, default=False):
        user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            return True
        if user.crm_job_id and hasattr(user.crm_job_id, perm_name):
            return bool(getattr(user.crm_job_id, perm_name))
        val = getattr(user, perm_name, None)
        return bool(val if val is not None else default)

    @api.model
    def get_views(self, views, options=None):
        res = super(EquipmentMaster, self).get_views(views, options=options)
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            can_create = self._user_can('perm_equipment_create', False)
            can_write = self._user_can('perm_equipment_write', False)
            can_delete = self._user_can('perm_equipment_unlink', False)

            for vtype in ['form', 'list', 'tree', 'kanban']:
                if vtype in res.get('views', {}):
                    arch_str = res['views'][vtype].get('arch')
                    if arch_str:
                        doc = etree.fromstring(arch_str)
                        if not can_create:
                            doc.attrib['create'] = 'false'
                        if not can_write:
                            doc.attrib['edit'] = 'false'
                        if not can_delete:
                            doc.attrib['delete'] = 'false'
                        res['views'][vtype]['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            if operation == 'create' and not self._user_can('perm_equipment_create', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to create Equipment Master records."))
                return False
            if operation == 'write' and not self._user_can('perm_equipment_write', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to update Equipment Master records."))
                return False
            if operation == 'unlink' and not self._user_can('perm_equipment_unlink', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to delete Equipment Master records."))
                return False
        return super(EquipmentMaster, self).check_access_rights(operation, raise_exception=raise_exception)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            if not self._user_can('perm_equipment_create', False):
                raise UserError(_("Access Denied: You do not have permission to create Equipment Master records."))
        return super(EquipmentMaster, self).create(vals_list)

    def write(self, vals):
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            if not self._user_can('perm_equipment_write', False):
                raise UserError(_("Access Denied: You do not have permission to update Equipment Master records."))
        return super(EquipmentMaster, self).write(vals)

    def unlink(self):
        for rec in self:
            user = self.env.user
            if not user._is_admin() and not user.has_group('base.group_system'):
                if not self._user_can('perm_equipment_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Equipment Master records."))
        return super(EquipmentMaster, self).unlink()