# -*- coding: utf-8 -*-
import base64
import io
import os
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from odoo import http, _
from odoo.http import request

class UniversalAttachmentPreviewController(http.Controller):

    @http.route('/custom_crm/attachment/preview_content', type='json', auth='user')
    def get_preview_content(self, raw_b64=None, filename=None, res_model=None, res_id=None, field_name=None):
        """Universal endpoint to parse and convert attachments (DOCX, Excel, ZIP) for preview across all modules."""
        attachment_b64 = raw_b64
        fname = filename or ''

        # If res_model and res_id are provided, fetch from record directly if b64 is missing
        if (not attachment_b64 or len(attachment_b64) < 50) and res_model and res_id and field_name:
            try:
                rec = request.env[res_model].sudo().browse(int(res_id))
                if rec.exists():
                    attachment_b64 = getattr(rec, field_name, False) or attachment_b64
                    fname = getattr(rec, f"{field_name}_filename", '') or getattr(rec, 'filename', '') or getattr(rec, 'name', '') or fname
            except Exception:
                pass

        if not attachment_b64:
            return {'type': 'empty'}

        try:
            raw_bytes = base64.b64decode(attachment_b64)
            ext = fname.lower().split('.')[-1] if '.' in fname else ''

            # 1. ZIP Archive: return clean file list
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

            # 2. Word Documents (.docx, .doc): Convert via LibreOffice to PDF for 100% exact rendering
            elif ext in ('docx', 'doc'):
                libreoffice_bin = (
                    shutil.which('libreoffice') or
                    shutil.which('soffice') or
                    (os.path.exists('/usr/bin/libreoffice') and '/usr/bin/libreoffice') or
                    (os.path.exists('/usr/bin/soffice') and '/usr/bin/soffice') or
                    (os.path.exists('/usr/lib/libreoffice/program/soffice') and '/usr/lib/libreoffice/program/soffice') or
                    (os.path.exists(r'C:\Program Files\LibreOffice\program\soffice.exe') and r'C:\Program Files\LibreOffice\program\soffice.exe') or
                    (os.path.exists(r'C:\Program Files (x86)\LibreOffice\program\soffice.exe') and r'C:\Program Files (x86)\LibreOffice\program\soffice.exe')
                )

                if libreoffice_bin:
                    try:
                        with tempfile.TemporaryDirectory() as tmp_dir:
                            doc_path = os.path.join(tmp_dir, f'doc_preview.{ext}')
                            with open(doc_path, 'wb') as f:
                                f.write(raw_bytes)

                            user_profile_dir = os.path.join(tmp_dir, 'lo_profile')
                            os.makedirs(user_profile_dir, exist_ok=True)
                            cmd = [
                                libreoffice_bin,
                                '--headless',
                                '--invisible',
                                '--nocrashreport',
                                '--nodefault',
                                '--nofirststartwizard',
                                '--nolockcheck',
                                '--nologo',
                                '-env:UserInstallation=file://' + os.path.abspath(user_profile_dir).replace('\\', '/'),
                                '--convert-to',
                                'pdf:writer_pdf_Export',
                                doc_path,
                                '--outdir',
                                tmp_dir
                            ]
                            env = dict(os.environ)
                            env['HOME'] = tmp_dir
                            subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, env=env)

                            pdf_path = os.path.join(tmp_dir, 'doc_preview.pdf')
                            if not os.path.exists(pdf_path):
                                for f in os.listdir(tmp_dir):
                                    if f.endswith('.pdf'):
                                        pdf_path = os.path.join(tmp_dir, f)
                                        break

                            if os.path.exists(pdf_path):
                                with open(pdf_path, 'rb') as f:
                                    pdf_data = f.read()
                                return {
                                    'type': 'pdf_content',
                                    'filename': fname,
                                    'pdf_base64': base64.b64encode(pdf_data).decode('ascii'),
                                }
                    except Exception:
                        pass

                # Fallback to XML-based HTML parsing if LibreOffice is not installed
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                        if 'word/document.xml' not in z.namelist():
                            return {'type': 'docx_content', 'filename': fname, 'html': '<p class="text-muted">Empty document.</p>'}

                        xml_content = z.read('word/document.xml')
                        tree = ET.fromstring(xml_content)
                        ns = {
                            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                        }
                        body = tree.find('.//w:body', ns)
                        html_parts = []
                        if body is not None:
                            for p in body.findall('.//w:p', ns):
                                runs_text = []
                                for r in p.findall('.//w:r', ns):
                                    t = ''.join([elem.text for elem in r.findall('.//w:t', ns) if elem.text])
                                    if t:
                                        if r.find('.//w:b', ns) is not None:
                                            runs_text.append(f"<strong>{t}</strong>")
                                        else:
                                            runs_text.append(t)
                                if runs_text:
                                    html_parts.append(f"<p>{''.join(runs_text)}</p>")
                        return {
                            'type': 'docx_content',
                            'filename': fname,
                            'html': ''.join(html_parts) or '<p class="text-muted">No text content found.</p>',
                        }
                except Exception:
                    pass

            # 3. Excel / Spreadsheets (.xlsx, .xls, .csv)
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
                        'rows': rows[:250],
                    })
                elif ext == 'xlsx':
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
                        try:
                            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
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
                        except Exception:
                            pass
                elif ext == 'xls':
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

        return {'type': 'unsupported', 'filename': fname}
