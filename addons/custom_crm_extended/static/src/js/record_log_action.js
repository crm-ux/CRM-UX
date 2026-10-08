/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { Component, xml, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

// Cache for user's perm_log status
let _userCanLogCache = null;

async function checkUserCanLog() {
    if (Boolean(user.isAdmin)) {
        return true;
    }
    if (_userCanLogCache !== null) {
        return _userCanLogCache;
    }
    try {
        const canLog = await rpc("/web/dataset/call_kw", {
            model: "res.users",
            method: "check_perm_log",
            args: [],
            kwargs: {},
        });
        _userCanLogCache = Boolean(canLog);
    } catch (e) {
        _userCanLogCache = false;
    }
    return _userCanLogCache;
}

/**
 * Audit / Change History Dialog Component
 */
class RecordLogDialog extends Component {
    static template = xml`
        <Dialog title="title" size="'lg'">
            <div class="p-3" style="max-height: 65vh; overflow-y: auto;">
                <!-- Summary Card -->
                <div class="card mb-3 shadow-sm border-0 bg-light">
                    <div class="card-body py-2 px-3">
                        <div class="row g-2 text-muted small">
                            <div class="col-md-6">
                                <span class="fw-semibold text-dark">Created by: </span>
                                <span t-esc="state.createBy || 'N/A'"/>
                                <span class="ms-1" t-if="state.createDate">(<span t-esc="state.createDate"/>)</span>
                            </div>
                            <div class="col-md-6">
                                <span class="fw-semibold text-dark">Last Updated by: </span>
                                <span t-esc="state.writeBy || 'N/A'"/>
                                <span class="ms-1" t-if="state.writeDate">(<span t-esc="state.writeDate"/>)</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Loading State -->
                <div t-if="state.loading" class="text-center py-4 text-muted">
                    <i class="fa fa-spinner fa-spin fa-2x mb-2 d-block"/>
                    <span>Loading change log...</span>
                </div>

                <!-- Empty State -->
                <div t-if="!state.loading and state.logs.length === 0" class="text-center py-4 text-muted">
                    <i class="fa fa-info-circle fa-2x mb-2 text-secondary d-block"/>
                    <span>No tracked field modifications recorded for this entry.</span>
                </div>

                <!-- Log Timeline -->
                <div t-if="!state.loading and state.logs.length > 0" class="crm-log-timeline">
                    <div t-foreach="state.logs" t-as="entry" t-key="entry.id" class="border-bottom py-2">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="fw-semibold text-primary">
                                <i class="fa fa-user-circle me-1"/>
                                <span t-esc="entry.author"/>
                            </span>
                            <span class="text-muted small" t-esc="entry.date"/>
                        </div>
                        <ul class="list-unstyled mb-0 ps-3 small">
                            <li t-foreach="entry.changes" t-as="ch" t-key="ch.id" class="text-secondary py-1">
                                <span class="fw-semibold text-dark" t-esc="ch.field"/>: 
                                <span class="text-danger text-decoration-line-through me-1" t-if="ch.oldValue" t-esc="ch.oldValue"/>
                                <i class="fa fa-long-arrow-right mx-1 text-muted"/>
                                <span class="text-success fw-semibold" t-esc="ch.newValue || '(empty)'"/>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-secondary" t-on-click="() => this.props.close()">Close</button>
            </t>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        close: { type: Function },
        resModel: { type: String },
        resId: { type: Number },
        recordName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            loading: true,
            createBy: "",
            createDate: "",
            writeBy: "",
            writeDate: "",
            logs: [],
        });

        onWillStart(async () => {
            await this.loadLogs();
        });
    }

    get title() {
        const name = this.props.recordName ? ` - ${this.props.recordName}` : "";
        return `Audit Log${name}`;
    }

    async loadLogs() {
        const { resModel, resId } = this.props;
        try {
            // 1. Fetch record metadata
            const metadata = await rpc("/web/dataset/call_kw", {
                model: resModel,
                method: "get_metadata",
                args: [[resId]],
                kwargs: {},
            });
            if (metadata && metadata.length) {
                const meta = metadata[0];
                this.state.createBy = meta.create_uid ? meta.create_uid[1] : "System";
                this.state.createDate = meta.create_date || "";
                this.state.writeBy = meta.write_uid ? meta.write_uid[1] : "System";
                this.state.writeDate = meta.write_date || "";
            }

            // 2. Fetch tracked changes from mail.message and mail.tracking.value
            const messages = await rpc("/web/dataset/call_kw", {
                model: "mail.message",
                method: "search_read",
                args: [[
                    ["model", "=", resModel],
                    ["res_id", "=", resId],
                    ["tracking_value_ids", "!=", false],
                ]],
                kwargs: {
                    fields: ["id", "author_id", "date", "tracking_value_ids"],
                    order: "date desc, id desc",
                    limit: 50,
                },
            });

            if (messages && messages.length) {
                const allTrackingIds = messages.flatMap((m) => m.tracking_value_ids || []);
                let trackingMap = {};
                if (allTrackingIds.length) {
                    const trackingRecords = await rpc("/web/dataset/call_kw", {
                        model: "mail.tracking.value",
                        method: "read",
                        args: [allTrackingIds],
                        kwargs: {
                            fields: [
                                "id",
                                "field_info",
                                "old_value_char",
                                "new_value_char",
                                "old_value_integer",
                                "new_value_integer",
                                "old_value_float",
                                "new_value_float",
                                "old_value_datetime",
                                "new_value_datetime",
                            ],
                        },
                    });
                    for (const tr of trackingRecords) {
                        const fieldDesc = tr.field_info?.desc || tr.field_info?.name || "Field";
                        const oldVal = tr.old_value_char || tr.old_value_integer || tr.old_value_float || tr.old_value_datetime || "";
                        const newVal = tr.new_value_char || tr.new_value_integer || tr.new_value_float || tr.new_value_datetime || "";
                        trackingMap[tr.id] = {
                            id: tr.id,
                            field: fieldDesc,
                            oldValue: String(oldVal || ""),
                            newValue: String(newVal || ""),
                        };
                    }
                }

                this.state.logs = messages.map((m) => ({
                    id: m.id,
                    author: m.author_id ? m.author_id[1] : "System",
                    date: m.date || "",
                    changes: (m.tracking_value_ids || []).map((tid) => trackingMap[tid]).filter(Boolean),
                })).filter((entry) => entry.changes.length > 0);
            }
        } catch (e) {
            console.error("Failed to load audit logs:", e);
        } finally {
            this.state.loading = false;
        }
    }
}

class RecordLogMenuItem extends Component {
    static template = xml`
        <span class="dropdown-item d-flex align-items-center cursor-pointer" role="menuitem" t-on-click="onSelected">
            <i class="fa fa-history me-2"/>
            <span>Log</span>
        </span>
    `;

    async onSelected() {
        const env = this.env;
        const resModel = env.config?.resModel || env.searchModel?.resModel || env.model?.root?.resModel;
        const resId = env.model?.root?.resId || env.config?.currentId;
        const recordName = env.model?.root?.data?.display_name || env.model?.root?.data?.name || "";

        if (resModel && resId) {
            env.services.dialog.add(RecordLogDialog, {
                resModel: resModel,
                resId: resId,
                recordName: recordName,
            });
        }
    }
}

import { registry } from "@web/core/registry";
const cogMenuRegistry = registry.category("cogMenu");

cogMenuRegistry.add("record_log_view", {
    isDisplayed: async (env) => {
        const viewType = env.config?.viewType;
        const isForm = viewType === "form";
        const resId = env.model?.root?.resId || env.config?.currentId;
        if (!isForm || !resId) {
            return false;
        }
        return await checkUserCanLog();
    },
    Component: RecordLogMenuItem,
    groupNumber: 20,
    sequence: 50,
});

