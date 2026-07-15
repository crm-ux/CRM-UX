/** @odoo-module **/
import { Component, useRef, onMounted, onPatched, useEffect } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ImageField } from "@web/views/fields/image/image_field";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

class ImageCropperDialog extends Component {
    static template = "exhibition_contacts.ImageCropperDialog";
    static components = { Dialog };
    static props = ["src", "onSave", "close"];

    setup() {
        this.cropperRef = useRef("cropperImg");
        this.cropper = null;
        onMounted(() => this.initCropper());
    }

    async initCropper() {
        if (!window.Cropper) {
            await this.loadScript("https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.js");
            await this.loadCSS("https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.css");
        }
        this.cropper = new window.Cropper(this.cropperRef.el, {
            aspectRatio: NaN, viewMode: 1, autoCropArea: 1,
        });
    }

    loadScript(src) {
        return new Promise((r) => { const s = document.createElement("script"); s.src = src; s.onload = r; document.head.appendChild(s); });
    }
    loadCSS(href) {
        return new Promise((r) => { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = href; l.onload = r; document.head.appendChild(l); });
    }
    rotateLeft() { this.cropper && this.cropper.rotate(-90); }
    rotateRight() { this.cropper && this.cropper.rotate(90); }
    flipH() { if (this.cropper) { const d = this.cropper.getData(); this.cropper.scaleX(d.scaleX === -1 ? 1 : -1); } }
    flipV() { if (this.cropper) { const d = this.cropper.getData(); this.cropper.scaleY(d.scaleY === -1 ? 1 : -1); } }
    reset() { this.cropper && this.cropper.reset(); }
    save() {
        if (!this.cropper) return;
        const base64 = this.cropper.getCroppedCanvas({ maxWidth: 1200, maxHeight: 1200 }).toDataURL("image/jpeg", 0.85).split(",")[1];
        this.props.onSave(base64);
        this.props.close();
    }
}

patch(ImageField.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
        // Make image clickable to open file picker
        useEffect(
            (el) => {
                if (!el || this.props.name !== "visiting_card") return;
                const img = el.querySelector("img");
                const uploader = el.querySelector(".o_image_uploader_container");
                const clickHandler = () => {
                    const input = el.querySelector("input[type=file]");
                    if (input) input.click();
                };
                if (img) { img.style.cursor = "pointer"; img.addEventListener("click", clickHandler); }
                if (uploader) { uploader.style.opacity = "1"; }
                return () => { if (img) img.removeEventListener("click", clickHandler); };
            },
            () => [document.querySelector(`[name="${this.props.name}"]`)]
        );
    },

    async onFileUploaded(info) {
        if (this.props.name !== "visiting_card") {
            return super.onFileUploaded(...arguments);
        }
        const src = `data:image/jpeg;base64,${info.data}`;
        this.dialogService.add(ImageCropperDialog, {
            src,
            onSave: (base64) => {
                this.props.record.update({ [this.props.name]: base64 });
            },
        });
    }
});
