/* Shared admin rich-text editor.
   Initialises every element with data-rich-editor-root that contains a textarea
   flagged with data-rich-editor="1". Image uploads POST to the URL set on
   document.body via data-editor-upload-url; falls back to /api/editor-upload/. */

(function () {
    'use strict';

    function getEditorCsrfToken() {
        if (window.siteUtils && typeof window.siteUtils.getCookie === 'function') {
            return window.siteUtils.getCookie('csrftoken') || '';
        }
        var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function getEditorUploadUrl() {
        var body = document.body;
        var url = body && body.getAttribute('data-editor-upload-url');
        return url || '/api/editor-upload/';
    }

    function insertHtmlAtCursor(editable, html) {
        editable.focus();
        if (document.queryCommandSupported && document.queryCommandSupported('insertHTML')) {
            document.execCommand('insertHTML', false, html);
            return;
        }
        var selection = window.getSelection();
        if (!selection || !selection.rangeCount) {
            editable.insertAdjacentHTML('beforeend', html);
            return;
        }
        var range = selection.getRangeAt(0);
        range.deleteContents();
        var fragment = range.createContextualFragment(html);
        range.insertNode(fragment);
    }

    function syncAllRichEditorInputs() {
        document.querySelectorAll('[data-rich-editor-root]').forEach(function (root) {
            if (root._richEditor && typeof root._richEditor.syncToTextarea === 'function') {
                root._richEditor.syncToTextarea();
            }
        });
    }

    function buildAdminRichEditor(root) {
        if (!root || root._richEditor) {
            return;
        }

        var textarea = root.querySelector('textarea[data-rich-editor="1"]');
        var editor = root.querySelector('[data-editor-editable]');
        var source = root.querySelector('[data-editor-source]');
        var sourceToggle = root.querySelector('[data-editor-source-toggle]');
        var formatSelect = root.querySelector('[data-editor-format]');
        var fontSizeSelect = root.querySelector('[data-editor-font-size]');
        var colorInput = root.querySelector('[data-editor-color]');
        var bgColorInput = root.querySelector('[data-editor-bg-color]');
        var imageInput = root.querySelector('[data-editor-image-input]');
        var imageTools = root.querySelector('[data-editor-image-tools]');
        var imageWidthInput = root.querySelector('[data-editor-image-width]');
        var imageWidthLabel = root.querySelector('[data-editor-image-width-label]');
        var imageAlignButtons = Array.prototype.slice.call(root.querySelectorAll('[data-editor-image-align]'));
        var imageResetButton = root.querySelector('[data-editor-image-reset]');

        if (!textarea || !editor || !source) {
            return;
        }

        var state = { sourceMode: false, selectedImage: null };
        textarea.classList.add('admin-rich-editor__hidden');
        textarea.style.display = 'none';
        editor.innerHTML = (textarea.value || '').trim() || '<p></p>';
        source.value = textarea.value || '';

        function syncToTextarea() {
            if (state.sourceMode) {
                textarea.value = source.value.trim();
            } else {
                textarea.value = editor.innerHTML.trim();
                source.value = textarea.value;
            }
            if (!textarea.value) {
                textarea.value = '';
            }
        }

        function syncFromSource() {
            editor.innerHTML = source.value.trim() || '<p></p>';
            textarea.value = source.value.trim();
        }

        function clampImageWidth(value) {
            var parsed = parseInt(value || '100', 10);
            if (Number.isNaN(parsed)) parsed = 100;
            return Math.min(100, Math.max(20, parsed));
        }

        function setImageToolsDisabled(disabled) {
            if (imageTools) imageTools.classList.toggle('is-disabled', !!disabled);
            if (imageWidthInput) imageWidthInput.disabled = !!disabled;
            if (imageResetButton) imageResetButton.disabled = !!disabled;
            imageAlignButtons.forEach(function (button) { button.disabled = !!disabled; });
        }

        function normalizeEditorImage(image) {
            if (!image) return;
            image.style.maxWidth = '100%';
            image.style.height = 'auto';
            if (!image.style.display) image.style.display = 'block';
            if (!image.style.marginBottom) image.style.marginBottom = '14px';
        }

        function getSelectedImageWidth(image) {
            if (!image) return 100;
            var widthStyle = (image.style.width || '').trim();
            if (widthStyle.indexOf('%') > -1) return clampImageWidth(widthStyle.replace('%', ''));
            var widthAttribute = (image.getAttribute('width') || '').trim();
            if (/^\d+$/.test(widthAttribute)) {
                return clampImageWidth(Math.round((parseInt(widthAttribute, 10) / Math.max(editor.clientWidth || 1, 1)) * 100));
            }
            var imageRect = image.getBoundingClientRect();
            var editorRect = editor.getBoundingClientRect();
            if (imageRect.width && editorRect.width) {
                return clampImageWidth(Math.round((imageRect.width / editorRect.width) * 100));
            }
            return 100;
        }

        function getSelectedImageAlign(image) {
            if (!image) return 'left';
            var marginLeft = (image.style.marginLeft || '').trim();
            var marginRight = (image.style.marginRight || '').trim();
            if (marginLeft === 'auto' && marginRight === 'auto') return 'center';
            if (marginLeft === 'auto') return 'right';
            return 'left';
        }

        function clearEditorImageSelection() {
            if (state.selectedImage) state.selectedImage.classList.remove('is-selected');
            state.selectedImage = null;
        }

        function updateImageControls() {
            var selectedImage = state.selectedImage;
            if (selectedImage && !editor.contains(selectedImage)) {
                clearEditorImageSelection();
                selectedImage = null;
            }

            var disabled = state.sourceMode || !selectedImage;
            setImageToolsDisabled(disabled);

            imageAlignButtons.forEach(function (button) { button.classList.remove('is-active'); });

            if (imageWidthInput) {
                imageWidthInput.value = disabled ? '100' : String(getSelectedImageWidth(selectedImage));
            }
            if (imageWidthLabel) {
                imageWidthLabel.textContent = (imageWidthInput ? imageWidthInput.value : '100') + '%';
            }

            if (disabled) return;

            normalizeEditorImage(selectedImage);
            var selectedAlign = getSelectedImageAlign(selectedImage);
            imageAlignButtons.forEach(function (button) {
                button.classList.toggle('is-active', button.getAttribute('data-editor-image-align') === selectedAlign);
            });
        }

        function selectEditorImage(image) {
            if (!image || state.sourceMode) {
                clearEditorImageSelection();
                updateImageControls();
                return;
            }
            if (state.selectedImage && state.selectedImage !== image) {
                state.selectedImage.classList.remove('is-selected');
            }
            state.selectedImage = image;
            normalizeEditorImage(image);
            image.classList.add('is-selected');
            updateImageControls();
        }

        function applySelectedImageWidth(value) {
            if (!state.selectedImage || state.sourceMode) return;
            var resolvedWidth = clampImageWidth(value);
            normalizeEditorImage(state.selectedImage);
            state.selectedImage.style.width = resolvedWidth + '%';
            state.selectedImage.removeAttribute('width');
            syncToTextarea();
            updateImageControls();
        }

        function applySelectedImageAlignment(alignment) {
            if (!state.selectedImage || state.sourceMode) return;
            normalizeEditorImage(state.selectedImage);
            if (alignment === 'center') {
                state.selectedImage.style.marginLeft = 'auto';
                state.selectedImage.style.marginRight = 'auto';
            } else if (alignment === 'right') {
                state.selectedImage.style.marginLeft = 'auto';
                state.selectedImage.style.marginRight = '0';
            } else {
                state.selectedImage.style.marginLeft = '0';
                state.selectedImage.style.marginRight = 'auto';
            }
            syncToTextarea();
            updateImageControls();
        }

        function refreshActiveStates() {
            root.querySelectorAll('[data-editor-command]').forEach(function (button) {
                var command = button.getAttribute('data-editor-command');
                if (!command || state.sourceMode) {
                    button.classList.remove('is-active');
                    return;
                }
                try {
                    var active = document.queryCommandState(command);
                    button.classList.toggle('is-active', !!active);
                } catch (error) {
                    button.classList.remove('is-active');
                }
            });
            updateImageControls();
        }

        function execEditorCommand(command, value) {
            if (state.sourceMode) { source.focus(); return; }
            editor.focus();
            document.execCommand(command, false, value || null);
            syncToTextarea();
            refreshActiveStates();
        }

        root.querySelectorAll('[data-editor-command]').forEach(function (button) {
            button.addEventListener('click', function () {
                execEditorCommand(button.getAttribute('data-editor-command'));
            });
        });

        if (formatSelect) {
            formatSelect.addEventListener('change', function () {
                execEditorCommand('formatBlock', formatSelect.value || 'p');
            });
        }
        if (fontSizeSelect) {
            fontSizeSelect.addEventListener('change', function () {
                execEditorCommand('fontSize', fontSizeSelect.value || '3');
            });
        }
        if (colorInput) {
            colorInput.addEventListener('input', function () { execEditorCommand('foreColor', colorInput.value); });
        }
        if (bgColorInput) {
            bgColorInput.addEventListener('input', function () { execEditorCommand('hiliteColor', bgColorInput.value); });
        }
        if (imageWidthInput) {
            imageWidthInput.addEventListener('input', function () { applySelectedImageWidth(imageWidthInput.value); });
        }
        imageAlignButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                applySelectedImageAlignment(button.getAttribute('data-editor-image-align') || 'left');
            });
        });
        if (imageResetButton) {
            imageResetButton.addEventListener('click', function () {
                applySelectedImageWidth(100);
                applySelectedImageAlignment('center');
            });
        }

        var linkButton = root.querySelector('[data-editor-link]');
        if (linkButton) {
            linkButton.addEventListener('click', function () {
                if (state.sourceMode) return;
                var link = window.prompt('Nhập liên kết muốn chèn:', 'https://');
                if (link) execEditorCommand('createLink', link);
            });
        }

        var unlinkButton = root.querySelector('[data-editor-unlink]');
        if (unlinkButton) {
            unlinkButton.addEventListener('click', function () { execEditorCommand('unlink'); });
        }

        var removeFormatButton = root.querySelector('[data-editor-remove-format]');
        if (removeFormatButton) {
            removeFormatButton.addEventListener('click', function () { execEditorCommand('removeFormat'); });
        }

        var tableButton = root.querySelector('[data-editor-table]');
        if (tableButton) {
            tableButton.addEventListener('click', function () {
                var rows = parseInt(window.prompt('Số hàng muốn chèn:', '2') || '0', 10);
                var cols = parseInt(window.prompt('Số cột muốn chèn:', '2') || '0', 10);
                if (!rows || !cols || rows < 1 || cols < 1) return;
                var tableHtml = '<table style="width:100%;border-collapse:collapse" border="1">';
                for (var rowIndex = 0; rowIndex < rows; rowIndex += 1) {
                    tableHtml += '<tr>';
                    for (var colIndex = 0; colIndex < cols; colIndex += 1) {
                        tableHtml += '<td style="padding:8px">&nbsp;</td>';
                    }
                    tableHtml += '</tr>';
                }
                tableHtml += '</table><p></p>';
                if (state.sourceMode) {
                    source.value += tableHtml;
                    syncFromSource();
                    syncToTextarea();
                    return;
                }
                insertHtmlAtCursor(editor, tableHtml);
                syncToTextarea();
            });
        }

        var imageButton = root.querySelector('[data-editor-image]');
        if (imageButton && imageInput) {
            imageButton.addEventListener('click', function () { imageInput.click(); });
            imageInput.addEventListener('change', function () {
                var file = imageInput.files && imageInput.files[0];
                if (!file) return;
                var data = new FormData();
                data.append('upload', file);
                fetch(getEditorUploadUrl(), {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getEditorCsrfToken() },
                    body: data
                }).then(function (response) {
                    return response.json().then(function (payload) {
                        if (!response.ok || !payload.url) {
                            throw new Error(payload.error || 'Không thể tải ảnh lên.');
                        }
                        return payload.url;
                    });
                }).then(function (url) {
                    var uploadMarker = 'editor-upload-' + Date.now() + '-' + Math.floor(Math.random() * 100000);
                    var imageHtml = '<p><img src="' + url + '" alt="Hình minh họa" data-editor-upload-marker="' + uploadMarker + '" style="display:block;max-width:100%;width:100%;height:auto;margin:0 auto 14px;"></p>';
                    if (state.sourceMode) {
                        source.value += imageHtml.replace(/\sdata-editor-upload-marker="[^"]*"/, '');
                        syncFromSource();
                        syncToTextarea();
                    } else {
                        insertHtmlAtCursor(editor, imageHtml);
                        syncToTextarea();
                        window.requestAnimationFrame(function () {
                            var insertedImage = editor.querySelector('img[data-editor-upload-marker="' + uploadMarker + '"]');
                            if (insertedImage) {
                                insertedImage.removeAttribute('data-editor-upload-marker');
                                selectEditorImage(insertedImage);
                            }
                        });
                    }
                }).catch(function (error) {
                    window.alert(error.message || 'Không thể tải ảnh lên.');
                }).finally(function () {
                    imageInput.value = '';
                });
            });
        }

        if (sourceToggle) {
            sourceToggle.addEventListener('click', function () {
                state.sourceMode = !state.sourceMode;
                if (state.sourceMode) {
                    clearEditorImageSelection();
                    syncToTextarea();
                    source.value = textarea.value;
                    root.classList.add('is-source-mode');
                    sourceToggle.textContent = 'Soạn thảo';
                } else {
                    syncFromSource();
                    root.classList.remove('is-source-mode');
                    sourceToggle.textContent = 'Mã HTML';
                }
                syncToTextarea();
                refreshActiveStates();
            });
        }

        editor.addEventListener('click', function (event) {
            var targetImage = event.target.closest('img');
            if (targetImage && editor.contains(targetImage)) {
                selectEditorImage(targetImage);
                return;
            }
            clearEditorImageSelection();
            updateImageControls();
        });

        editor.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                clearEditorImageSelection();
                updateImageControls();
            }
        });

        ['input', 'blur', 'keyup', 'paste', 'mouseup'].forEach(function (eventName) {
            editor.addEventListener(eventName, function () {
                syncToTextarea();
                refreshActiveStates();
            });
        });
        source.addEventListener('input', function () { syncToTextarea(); });

        root._richEditor = { syncToTextarea: syncToTextarea };
        syncToTextarea();
        refreshActiveStates();
    }

    function ensureRichEditors() {
        document.querySelectorAll('[data-rich-editor-root]').forEach(function (root) {
            buildAdminRichEditor(root);
        });
    }

    document.addEventListener('DOMContentLoaded', ensureRichEditors);

    document.addEventListener('submit', function (event) {
        if (event.target && event.target.tagName === 'FORM' && event.target.querySelector('[data-rich-editor-root]')) {
            syncAllRichEditorInputs();
        }
    }, true);

    window.ensureAdminRichEditors = ensureRichEditors;
    window.syncAdminRichEditors = syncAllRichEditorInputs;
})();
