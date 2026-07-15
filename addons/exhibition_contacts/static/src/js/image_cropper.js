/** @odoo-module **/
import { Component, useRef, onMounted } from "@odoo/owl";
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
        const img = this.cropperRef.el;
        this.cropper = new window.Cropper(img, {
            aspectRatio: NaN,
            viewMode: 1,
            autoCropArea: 1,
        });
    }

    loadScript(src) {
        return new Promise((resolve) => {
            const script = document.createElement("script");
            script.src = src;
            script.onload = resolve;
            document.head.appendChild(script);
        });
    }

    loadCSS(href) {
        return new Promise((resolve) => {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = href;
            link.onload = resolve;
            document.head.appendChild(link);
        });
    }

    rotateLeft() { this.cropper && this.cropper.rotate(-90); }
    rotateRight() { this.cropper && this.cropper.rotate(90); }
    flipH() { 
        if (this.cropper) {
            const data = this.cropper.getData();
            this.cropper.scaleX(data.scaleX === -1 ? 1 : -1);
        }
    }
    flipV() {
        if (this.cropper) {
            const data = this.cropper.getData();
            this.cropper.scaleY(data.scaleY === -1 ? 1 : -1);
        }
    }
    reset() { this.cropper && this.cropper.reset(); }

    save() {
        if (!this.cropper) return;
        const canvas = this.cropper.getCroppedCanvas({ maxWidth: 1200, maxHeight: 1200 });
        const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
        const base64 = dataUrl.split(",")[1];
        this.props.onSave(base64);
        this.props.close();
    }
}

patch(ImageField.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
    },

    async onFileUploaded(info) {
        // Only intercept for visiting_card field
        if (this.props.name !== "visiting_card") {
            return super.onFileUploaded(...arguments);
        }
        const { data } = info;
        const src = `data:image/jpeg;base64,${data}`;
        this.dialogService.add(ImageCropperDialog, {
            src,
            onSave: (base64) => {
                this.props.record.update({ [this.props.name]: base64 });
            },
        });
    }
});
