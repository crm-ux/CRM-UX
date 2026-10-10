/** @odoo-module **/

import { Component, xml, useState, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

export class AssignWorkModalDialog extends Component {
    static template = xml`
        <Dialog title="'Assign Work'" size="'md'" contentClass="'p-0'" footer="false">
            <div class="crm-assign-work-modal-body" style="padding: 1.25rem; display: flex; flex-direction: column; gap: 0.95rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                
                <!-- 1. Select Team Member -->
                <div>
                    <label style="display: block; font-size: 0.8rem; font-weight: 700; color: #1e293b; margin-bottom: 0.35rem;">
                        Assign To <span style="color: #ef4444;">*</span>
                    </label>
                    
                    <!-- Search Member Input -->
                    <div style="position: relative; margin-bottom: 0.5rem;">
                        <i class="fa fa-search" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8; font-size: 0.85rem;"></i>
                        <input type="text" 
                               placeholder="Search team member by name or login..." 
                               t-model="state.taskMemberSearch" 
                               t-on-input="onMemberSearchInput"
                               style="width: 100%; padding: 0.45rem 0.75rem 0.45rem 2.1rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.82rem; outline: none;"/>
                    </div>

                    <!-- Scrollable Member List -->
                    <div style="max-height: 140px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; padding: 0.25rem;">
                        <t t-if="state.loadingUsers">
                            <div style="padding: 0.75rem; text-align: center; color: #64748b; font-size: 0.82rem;">Loading team members...</div>
                        </t>
                        <t t-elif="state.assignableUsers.length === 0">
                            <div style="padding: 0.75rem; text-align: center; color: #94a3b8; font-size: 0.82rem;">No matching team members found.</div>
                        </t>
                        <t t-foreach="state.assignableUsers" t-as="u" t-key="u.id">
                            <div t-on-click="() => this.selectUser(u)" 
                                 t-att-style="state.selectedUser and state.selectedUser.id === u.id ? 'display: flex; align-items: center; gap: 10px; padding: 0.45rem 0.65rem; border-radius: 6px; background: #e0f2fe; border: 1px solid #0284c7; cursor: pointer;' : 'display: flex; align-items: center; gap: 10px; padding: 0.45rem 0.65rem; border-radius: 6px; background: #ffffff; margin-bottom: 2px; cursor: pointer; border: 1px solid transparent;'">
                                <div style="width: 28px; height: 28px; border-radius: 50%; background: #0b3d91; color: #ffffff; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0;">
                                    <t t-esc="u.name[0].toUpperCase()"/>
                                </div>
                                <div style="flex: 1; min-width: 0;">
                                    <div style="font-size: 0.82rem; font-weight: 700; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                        <t t-esc="u.name"/>
                                        <small t-if="u.job_title" style="color: #64748b; font-weight: normal; margin-left: 6px;">(<t t-esc="u.job_title"/>)</small>
                                    </div>
                                    <div style="font-size: 0.72rem; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                        <span t-if="u.department"><t t-esc="u.department"/> · </span><t t-esc="u.email or u.login"/>
                                    </div>
                                </div>
                                <i t-if="state.selectedUser and state.selectedUser.id === u.id" class="fa fa-check-circle" style="color: #0284c7; font-size: 1rem;"></i>
                            </div>
                        </t>
                    </div>
                </div>

                <!-- 2. Task Title & Due Date -->
                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 0.75rem;">
                    <div>
                        <label style="display: block; font-size: 0.8rem; font-weight: 700; color: #1e293b; margin-bottom: 0.35rem;">
                            Task Title <span style="color: #ef4444;">*</span>
                        </label>
                        <input type="text" 
                               placeholder="e.g. Inspect Boiler Unit 3" 
                               t-model="state.taskTitle"
                               style="width: 100%; padding: 0.45rem 0.75rem; font-size: 0.85rem; border-radius: 6px; border: 1px solid #cbd5e1; outline: none;"/>
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.8rem; font-weight: 700; color: #1e293b; margin-bottom: 0.35rem;">
                            Deadline
                        </label>
                        <input type="date" 
                               t-model="state.taskDeadline"
                               style="width: 100%; padding: 0.45rem 0.5rem; font-size: 0.82rem; border-radius: 6px; border: 1px solid #cbd5e1; outline: none;"/>
                    </div>
                </div>

                <!-- 3. Notes / Work Details -->
                <div>
                    <label style="display: block; font-size: 0.8rem; font-weight: 700; color: #1e293b; margin-bottom: 0.35rem;">Work Details / Instructions</label>
                    <textarea placeholder="Add instructions or requirements for this task..." 
                              t-model="state.taskNote"
                              style="min-height: 70px; font-size: 0.85rem; border-radius: 6px; border: 1px solid #cbd5e1; padding: 0.5rem 0.75rem; width: 100%; outline: none;"></textarea>
                </div>

                <!-- 4. Attachment Field -->
                <div>
                    <label style="display: block; font-size: 0.8rem; font-weight: 700; color: #1e293b; margin-bottom: 0.35rem;">
                        Attachment
                    </label>
                    
                    <div t-if="!state.attachmentName" style="border: 2px dashed #cbd5e1; border-radius: 6px; padding: 0.75rem; text-align: center; background: #f8fafc; cursor: pointer; position: relative;">
                        <i class="fa fa-cloud-upload" style="font-size: 1.4rem; color: #0b3d91; margin-bottom: 0.25rem;"></i>
                        <div style="font-size: 0.8rem; color: #475569; font-weight: 600;">Click to upload file (up to 20MB)</div>
                        <input type="file" 
                               t-on-change="onAttachmentChange" 
                               style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer;"/>
                    </div>

                    <div t-if="state.attachmentName" style="display: flex; align-items: center; justify-content: space-between; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.45rem 0.75rem;">
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.82rem; color: #1e293b; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            <i class="fa fa-file-pdf-o" style="color: #0b3d91;"></i>
                            <span t-esc="state.attachmentName"/>
                        </div>
                        <button type="button" 
                                t-on-click="removeAttachment" 
                                style="border: none; background: none; color: #ef4444; font-size: 0.85rem; cursor: pointer;" 
                                title="Remove attachment">✕</button>
                    </div>
                </div>

                <!-- Footer Actions -->
                <div style="padding-top: 0.75rem; border-top: 1px solid #e2e8f0; display: flex; justify-content: flex-end; gap: 0.5rem;">
                    <button class="btn btn-secondary" t-on-click="() => this.props.close()" style="padding: 0.45rem 1rem; border-radius: 6px; border: 1px solid #cbd5e1; background: #ffffff; color: #475569; font-weight: 600; cursor: pointer;">Cancel</button>
                    <button class="btn btn-primary" 
                            t-att-disabled="state.submitting"
                            t-on-click="submitAssignment" 
                            style="padding: 0.45rem 1.25rem; border-radius: 6px; border: none; background: #0b3d91; color: #ffffff; font-weight: 600; cursor: pointer;">
                        <t t-if="state.submitting">Assigning...</t>
                        <t t-else="">Assign Work</t>
                    </button>
                </div>

            </div>
        </Dialog>
    `;

    static components = { Dialog };

    setup() {
        this.state = useState({
            selectedUser: null,
            taskTitle: "",
            taskNote: "",
            taskDeadline: new Date().toISOString().split("T")[0],
            taskMemberSearch: "",
            attachmentName: "",
            attachmentData: null,
            assignableUsers: [],
            loadingUsers: true,
            submitting: false,
        });

        onMounted(() => {
            this.loadUsers();
        });
    }

    async loadUsers() {
        this.state.loadingUsers = true;
        const uid = this.props.viewAsUserId || user.userId;
        try {
            const members = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "get_assignable_team_members",
                args: [],
                kwargs: { user_id: uid, search_term: "" },
            });
            this.state.assignableUsers = members || [];
        } catch (e) {
            console.error("Error loading team members:", e);
            this.state.assignableUsers = [];
        } finally {
            this.state.loadingUsers = false;
        }
    }

    async onMemberSearchInput(ev) {
        const val = ev.target.value || "";
        this.state.taskMemberSearch = val;
        const uid = this.props.viewAsUserId || user.userId;
        try {
            const members = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "get_assignable_team_members",
                args: [],
                kwargs: { user_id: uid, search_term: val },
            });
            this.state.assignableUsers = members || [];
        } catch (e) {
            console.error("Error searching team members:", e);
        }
    }

    selectUser(u) {
        this.state.selectedUser = u;
    }

    onAttachmentChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            this.state.attachmentName = "";
            this.state.attachmentData = null;
            return;
        }
        if (file.size > 20 * 1024 * 1024) {
            alert("File size cannot exceed 20MB.");
            ev.target.value = "";
            return;
        }
        this.state.attachmentName = file.name;
        const reader = new FileReader();
        reader.onload = (e) => {
            const base64 = e.target.result.split(",")[1];
            this.state.attachmentData = base64;
        };
        reader.readAsDataURL(file);
    }

    removeAttachment() {
        this.state.attachmentName = "";
        this.state.attachmentData = null;
    }

    async submitAssignment() {
        if (!this.state.selectedUser) {
            alert("Please select a team member to assign the task to.");
            return;
        }
        if (!this.state.taskTitle || !this.state.taskTitle.trim()) {
            alert("Please enter a task title.");
            return;
        }

        this.state.submitting = true;
        try {
            const deadline = this.state.taskDeadline || new Date().toISOString().split("T")[0];
            const assignRes = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "assign_team_task",
                args: [this.state.selectedUser.id, this.state.taskTitle.trim()],
                kwargs: {
                    note: this.state.taskNote ? this.state.taskNote.trim() : "",
                    deadline: deadline,
                    attachment_name: this.state.attachmentName || "",
                    attachment_data: this.state.attachmentData || "",
                },
            });

            if (assignRes && assignRes.success === false) {
                alert("Failed to assign task: " + (assignRes.error || "Unknown error"));
                return;
            }

            this.props.close();
            if (this.props.onSuccess) {
                await this.props.onSuccess(this.state.selectedUser);
            }
        } catch (e) {
            console.error("Assign task error:", e);
            alert("Error: " + (e?.data?.message || e?.message || "Server Error"));
        } finally {
            this.state.submitting = false;
        }
    }
}
