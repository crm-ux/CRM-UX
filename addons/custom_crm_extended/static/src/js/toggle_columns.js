/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { onMounted, onPatched } from "@odoo/owl";

patch(ListRenderer.prototype, {
    computeOptionalActiveFields() {
        const result = super.computeOptionalActiveFields(...arguments);
        try {
            const parentRecord = this.props?.list?.model?.root;
            if (parentRecord && parentRecord.resModel === 'sale.order') {
                const showGST = parentRecord.data?.x_gst_included ?? false;
                const showMargin = parentRecord.data?.x_show_cost_profit ?? false;
                if ('tax_ids' in result) {
                    result['tax_ids'] = showGST;
                }
                if ('x_cost' in result) {
                    result['x_cost'] = showMargin;
                    result['x_profit'] = showMargin;
                    result['x_profit_pct'] = showMargin;
                }
            }
        } catch (e) { }
        return result;
    },

    getSectionSubtotal(record) {
        const parentRecord = this.props?.list?.model?.root;
        if (parentRecord && parentRecord.resModel === 'sale.order') {
            return ""; // Completely stop calculating or showing any subtotal on section rows!
        }
        return super.getSectionSubtotal ? super.getSectionSubtotal(...arguments) : "";
    },

    async onDeleteRecord(record) {
        const parentRecord = this.props?.list?.model?.root;
        if (parentRecord && parentRecord.resModel === 'sale.order' && record.data?.display_type === 'line_section') {
            // When deleting a section header, only delete this 1 single record — NEVER delete products below it!
            await record.delete();
            return;
        }
        return super.onDeleteRecord ? super.onDeleteRecord(...arguments) : record.delete();
    },

    setup() {
        super.setup ? super.setup() : null;

        const checkEmptyState = () => {
            const resModel = this.props?.list?.resModel;
            if (resModel === 'crm.personal.todo' || resModel === 'crm.task.management') {
                const count = this.props?.list?.records?.length ?? 0;
                const el = this.rootRef?.el || (this.el ? this.el : document.querySelector(".o_list_renderer"));
                if (!el) return;
                
                // Remove Odoo default duplicate empty container if present
                const defaultEmpty = el.querySelector(".o_view_nocontent:not(.crm-custom-empty-state)");
                if (defaultEmpty) {
                    defaultEmpty.style.display = "none";
                }

                let emptyEl = el.querySelector(".crm-custom-empty-state");
                if (count === 0) {
                    const table = el.querySelector("table.o_list_table");
                    if (table) table.style.display = "none";
                    if (!emptyEl) {
                        emptyEl = document.createElement("div");
                        emptyEl.className = "o_view_nocontent crm-custom-empty-state";
                        emptyEl.style.cssText = "display: flex !important; flex-direction: column; align-items: center; justify-content: center; min-height: 45vh; text-align: center; width: 100%; margin: 2rem auto;";
                        emptyEl.innerHTML = `
                            <div class="o_nocontent_help" style="display: block !important;">
                                <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="120" height="140" viewBox="0 0 120 140" style="margin-bottom: 1rem; display: inline-block;">
                                    <defs>
                                        <linearGradient id="empty_state_blue_bg" x1="91.284%" x2="25.707%" y1="100%" y2="0%">
                                            <stop offset="0%" stop-color="#0d3e8e"/>
                                            <stop offset="100%" stop-color="#07224f"/>
                                        </linearGradient>
                                        <circle id="empty_state_circle" cx="56" cy="76.614" r="56"/>
                                        <filter id="empty_state_shadow" width="112.5%" height="112.5%" x="-6.2%" y="-4.5%" filterUnits="objectBoundingBox">
                                            <feOffset dy="2" in="SourceAlpha" result="shadowOffsetOuter1"/>
                                            <feGaussianBlur in="shadowOffsetOuter1" result="shadowBlurOuter1" stdDeviation="2"/>
                                            <feColorMatrix in="shadowBlurOuter1" values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.12 0"/>
                                        </filter>
                                        <path id="empty_state_clip" d="M56,122.807 C86.928,122.807 112,97.672 112,66.667 C112,59.661 112,37.438 112,0 L0,0 C0,23.774 0,45.996 0,66.667 C0,97.672 25.072,122.807 56,122.807 Z"/>
                                        <path id="empty_state_paper" d="M22,6.015 L84.315,6.015 L100.5,22.556 L100.5,114.83 C100.5,124.218 92.889,131.83 83.5,131.83 L31,131.83 C21.611,131.83 14,124.218 14,114.83 L14,14.015 C14,9.597 17.582,6.015 22,6.015 Z"/>
                                    </defs>
                                    <g fill="none" fill-rule="evenodd" transform="translate(4 2)">
                                        <use fill="#000" filter="url(#empty_state_shadow)" xlink:href="#empty_state_circle"/>
                                        <use fill="url(#empty_state_blue_bg)" xlink:href="#empty_state_circle"/>
                                        <g transform="translate(0 10)">
                                            <mask id="empty_state_mask" fill="#fff">
                                                <use xlink:href="#empty_state_clip"/>
                                            </mask>
                                            <g mask="url(#empty_state_mask)">
                                                <use fill="#FFF" xlink:href="#empty_state_paper"/>
                                                <path stroke="#A1ACBA" stroke-width="2" d="M99.5,22.964 L83.894,7.015 L22,7.015 C18.134,7.015 15,10.149 15,14.015 L15,114.83 C15,123.666 22.163,130.83 31,130.83 L83.5,130.83 C92.337,130.83 99.5,123.666 99.5,114.83 L99.5,22.964 Z"/>
                                            </g>
                                            <path stroke="#A1ACBA" stroke-width="2" d="M84.8,27.505 C87.406,25.022 91.415,21.266 91.788,20.627 C92.092,20.105 92.201,19.57 92.201,18.554 C92.201,17.921 92.06,17.314 91.766,16.678 C91.275,15.614 90.368,14.469 88.765,12.838 C88.239,12.302 86.319,10.445 84.8,8.968 L84.8,27.505 Z" mask="url(#empty_state_mask)" transform="rotate(135 88.5 18.226)"/>
                                            <g fill="#000" mask="url(#empty_state_mask)" opacity=".07">
                                                <g transform="translate(23 81)">
                                                    <rect width="46.716" height="6.214"/>
                                                    <rect width="68.812" height="6.214" y="8.7"/>
                                                    <rect width="42.297" height="6.214" y="20.506"/>
                                                    <rect width="52.398" height="6.214" y="31.07"/>
                                                </g>
                                            </g>
                                        </g>
                                        <path stroke="#38bdf8" stroke-linecap="round" stroke-width="2" d="M13 14L4 5M18 9L18 0M1 20L10 20"/>
                                        <g transform="translate(28.491 43.21)">
                                            <path stroke="#334155" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M11.509,17.789 C28.009,26.789 44.509,17.789 44.509,17.789"/>
                                            <circle cx="48.009" cy="5.289" r="3.5" fill="#334155"/>
                                            <circle cx="8.009" cy="5.289" r="3.5" fill="#334155"/>
                                        </g>
                                    </g>
                                </svg>
                                <h4 style="font-weight: 700; color: #0d3e8e; margin: 0.5rem 0 0.35rem 0; font-size: 1.35rem;">
                                    ${resModel === 'service.ticket.voucher.batch' ? 'No vouchers yet' : 'No tasks yet'}
                                </h4>
                                <p class="text-muted" style="margin: 0; font-size: 0.95rem; max-width: 450px;">
                                    ${resModel === 'crm.personal.todo' ? 'Keep track of your personal notes, reminders, and daily checklist here.' : (resModel === 'service.ticket.voucher.batch' ? 'All submitted expense vouchers and batches will appear here.' : 'Track activities, assign work to team members, and monitor progress here.')}
                                </p>
                            </div>
                        `;
                        el.appendChild(emptyEl);
                    }
                } else {
                    if (emptyEl) emptyEl.remove();
                    const table = el.querySelector("table.o_list_table");
                    if (table) table.style.display = "";
                }
            }
        };
        onMounted(checkEmptyState);
        onPatched(checkEmptyState);

        const parentRecord = this.props?.list?.model?.root;
        if (parentRecord && parentRecord.resModel === 'sale.order') {
            // Intercept click on the section options button to directly delete this single section row
            const handleSectionClick = async (ev) => {
                const btn = ev.target.closest("tr.o_is_line_section td.o_list_section_options button, tr.o_is_line_section .o_list_section_options");
                if (!btn) return;
                ev.preventDefault();
                ev.stopPropagation();
                ev.stopImmediatePropagation();

                const row = btn.closest("tr.o_is_line_section");
                const dataId = row?.getAttribute("data-id");
                if (dataId) {
                    const rec = this.props.list.records.find((r) => r.id === dataId);
                    if (rec) {
                        await rec.delete();
                    }
                }
            };
            this.handleSectionClick = handleSectionClick;
            document.addEventListener("click", this.handleSectionClick, true);
        }
    },
});
