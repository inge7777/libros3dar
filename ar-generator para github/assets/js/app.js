document.addEventListener('DOMContentLoaded', () => {
    // --- State Management ---
    const state = {
        files: {
            images: [],
            models: [],
            patterns: []
        },
        three: {
            scene: null,
            camera: null,
            renderer: null,
            controls: null,
            model: null,
            animationFrameId: null
        },
        currentPackagePath: null
    };

    // --- Element Caching ---
    const ui = {
        mainAppContainer: document.getElementById('main-app-container'),
        tabs: document.querySelectorAll('.tab'),
        tabContents: document.querySelectorAll('.tab-content'),
        imageUploadArea: document.getElementById('image-upload-area'),
        modelUploadArea: document.getElementById('model-upload-area'),
        imageInput: document.getElementById('image-input'),
        modelInput: document.getElementById('model-input'),
        imageList: document.getElementById('image-list'),
        modelList: document.getElementById('model-list'),
        modelSelector3D: document.getElementById('model-selector-3d'),
        threeModelViewer: document.getElementById('three-model-viewer'),
        ar: {
            viewBtn: document.getElementById('view-ar-btn')
        },
        generation: {
            appName: document.getElementById('app-name'),
            packageName: document.getElementById('package-name'),
            generatePattBtn: document.getElementById('generate-patt-btn'),
            generatePackageBtn: document.getElementById('generate-package-btn'),
            generateApkBtn: document.getElementById('generate-apk-btn'),
            apkDownloadContainer: document.getElementById('apk-download-container')
        },
        log: {
            panel: document.getElementById('log-panel'),
            content: document.getElementById('log-content'),
            toggleBtn: document.getElementById('log-toggle-btn'),
            clearBtn: document.getElementById('clear-log-btn'),
            resetBtn: document.getElementById('reset-all-btn')
        }
    };

    // --- Logging ---
    function log(message, type = 'info') {
        const colors = { info: '#00ff00', success: '#4caf50', error: '#f44336', warning: '#ff9800' };
        const icon = { info: 'fas fa-info-circle', success: 'fas fa-check-circle', error: 'fas fa-exclamation-triangle', warning: 'fas fa-exclamation-circle' };
        const entry = document.createElement('div');
        entry.style.color = colors[type] || colors.info;
        entry.innerHTML = `<i class="${icon[type] || icon.info} me-2"></i><span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> ${message}`;
        if (ui.log.content) {
            ui.log.content.appendChild(entry);
            ui.log.content.scrollTop = ui.log.content.scrollHeight;
        }
    }

    // --- UI Logic ---
    function setupEventListeners() {
        if (ui.tabs) ui.tabs.forEach(tab => tab.addEventListener('click', () => switchTab(tab.dataset.tab)));
        
        if (ui.imageUploadArea) ui.imageUploadArea.addEventListener('click', () => ui.imageInput.click());
        if (ui.modelUploadArea) ui.modelUploadArea.addEventListener('click', () => ui.modelInput.click());
        if (ui.imageInput) ui.imageInput.addEventListener('change', e => handleFileUpload(e.target.files, 'image'));
        if (ui.modelInput) ui.modelInput.addEventListener('change', e => handleFileUpload(e.target.files, 'model'));
        if (ui.imageUploadArea) setupDragAndDrop(ui.imageUploadArea, files => handleFileUpload(files, 'image'));
        if (ui.modelUploadArea) setupDragAndDrop(ui.modelUploadArea, files => handleFileUpload(files, 'model'));

        if (ui.modelSelector3D) ui.modelSelector3D.addEventListener('change', loadSelected3DModel);
        if (ui.ar.viewBtn) ui.ar.viewBtn.addEventListener('click', viewAR);

        if (ui.generation.generatePattBtn) ui.generation.generatePattBtn.addEventListener('click', generatePatterns);
        if (ui.generation.generatePackageBtn) ui.generation.generatePackageBtn.addEventListener('click', generatePackage);
        if (ui.generation.generateApkBtn) ui.generation.generateApkBtn.addEventListener('click', generateAPK);

        if (ui.log.toggleBtn) ui.log.toggleBtn.addEventListener('click', toggleLogPanel);
        if (ui.log.clearBtn) ui.log.clearBtn.addEventListener('click', clearLog);
        if (ui.log.resetBtn) ui.log.resetBtn.addEventListener('click', resetAll);
    }

    function switchTab(tabIndex) {
        if (ui.tabs) ui.tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.tab === tabIndex));
        if (ui.tabContents) ui.tabContents.forEach(content => content.classList.toggle('active', content.id === `tab-${tabIndex}`));
        if (tabIndex === '2') {
            loadSelected3DModel();
        }
    }

    function setupDragAndDrop(element, callback) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => element.addEventListener(eventName, e => { e.preventDefault(); e.stopPropagation(); }, false));
        ['dragenter', 'dragover'].forEach(eventName => element.addEventListener(eventName, () => element.classList.add('dragover'), false));
        ['dragleave', 'drop'].forEach(eventName => element.addEventListener(eventName, () => element.classList.remove('dragover'), false));
        element.addEventListener('drop', e => callback(e.dataTransfer.files), false);
    }

    function toggleLogPanel() {
        const isVisible = ui.log.panel.style.display === 'block';
        ui.log.panel.style.display = isVisible ? 'none' : 'block';
        ui.log.toggleBtn.classList.toggle('active', !isVisible);
    }

    function clearLog() {
        if (ui.log.content) {
            ui.log.content.innerHTML = '';
            log('Log limpiado.', 'info');
        }
    }

    // --- Data & API Logic ---
    async function refreshFileLists() {
        try {
            const response = await fetch('api/list_files.php');
            if (!response.ok) throw new Error(`El servidor respondió con el estado: ${response.status}`);
            const data = await response.json();
            if (data.success) {
                state.files.images = data.images || [];
                state.files.models = data.models || [];
                state.files.patterns = data.patterns || [];
                updateAllUILists();
                log('Listas de archivos refrescadas desde el servidor.', 'success');
            }
        } catch (error) {
            log(`No se pudieron refrescar las listas de archivos: ${error.message}`, 'warning');
        }
    }

    async function handleFileUpload(files, type) {
        if (!files || files.length === 0) return;
        log(`Subiendo ${files.length} archivo(s) de tipo '${type}'...`, 'info');
        const formData = new FormData();
        Array.from(files).forEach(file => formData.append('files[]', file));
        formData.append('type', type);

        try {
            const response = await fetch('api/upload.php', { method: 'POST', body: formData });
            if (!response.ok) throw new Error(`Error del servidor: ${response.statusText}`);
            const result = await response.json();
            if (result.success) {
                log(`${result.files.length} archivo(s) de tipo '${type}' subido(s) con éxito.`, 'success');
                refreshFileLists(); 
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            log(`Error en la subida: ${error.message}`, 'error');
        }
    }
    
    function updateAllUILists() {
        if (ui.imageList) {
            ui.imageList.innerHTML = state.files.images.map(f => `<div class="file-item">${f.name}</div>`).join('');
        }
        if (ui.modelList) {
            ui.modelList.innerHTML = state.files.models.map(f => `<div class="file-item">${f.name}</div>`).join('');
        }
        if (ui.modelSelector3D) {
            ui.modelSelector3D.innerHTML = '<option value="">-- Seleccione --</option>';
            state.files.models.forEach(m => ui.modelSelector3D.innerHTML += `<option value="${m.url}">${m.name}</option>`);
        }
    }

    async function generatePatterns() {
        if (state.files.images.length === 0) {
            return log('No hay imágenes para generar patrones. Sube imágenes primero en la pestaña "Cargar Contenido".', 'warning');
        }
        log('Generando patrones para las imágenes subidas...', 'info');
        const imageNames = state.files.images.map(img => img.name);
        try {
            const response = await fetch('api/generate_patterns.php', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ images: imageNames })
            });
            if (!response.ok) throw new Error(`Error del servidor: ${response.statusText}`);
            const result = await response.json();
            if (result.success) {
                log('Proceso de generación de patrones finalizado.', 'success');
                result.patterns.forEach(p => log(`- ${p.filename}: ${p.status === 'ok' ? 'Generado' : 'Error'}`, p.status === 'ok' ? 'success' : 'error'));
                refreshFileLists();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            log(`Error al generar patrones: ${error.message}`, 'error');
        }
    }

    // --- 3D & AR Rendering ---
    function initThreeViewer() {
        if (state.three.renderer) return;
        if (!ui.threeModelViewer) return;
        ui.threeModelViewer.innerHTML = "";
        
        const w = ui.threeModelViewer.offsetWidth;
        const h = ui.threeModelViewer.offsetHeight;

        state.three.scene = new THREE.Scene();
        state.three.scene.background = new THREE.Color(0xeeeeee);
        state.three.camera = new THREE.PerspectiveCamera(75, w / h, 0.1, 1000);
        state.three.camera.position.set(0, 1, 2);
        
        state.three.renderer = new THREE.WebGLRenderer({ antialias: true });
        state.three.renderer.setSize(w, h);
        ui.threeModelViewer.appendChild(state.three.renderer.domElement);
        
        state.three.controls = new THREE.OrbitControls(state.three.camera, state.three.renderer.domElement);
        state.three.scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.5));
        
        const animate = () => {
            state.three.animationFrameId = requestAnimationFrame(animate);
            if (state.three.controls) state.three.controls.update();
            if (state.three.renderer) state.three.renderer.render(state.three.scene, state.three.camera);
        };
        animate();
    }

    function cleanMaterial(material) {
        material.dispose();
        for (const key of Object.keys(material)) {
            const value = material[key];
            if (value && typeof value === 'object' && 'isTexture' in value) {
                value.dispose();
            }
        }
    }

    function loadSelected3DModel() {
        if (!ui.modelSelector3D) return;
        const url = ui.modelSelector3D.value;
        if (!url) return;
        
        initThreeViewer();
        
        if (state.three.model) {
            state.three.model.traverse(object => {
                if (object.isMesh) {
                    if (object.geometry) object.geometry.dispose();
                    if (object.material) {
                        if (Array.isArray(object.material)) {
                            object.material.forEach(cleanMaterial);
                        } else {
                            cleanMaterial(object.material);
                        }
                    }
                }
            });
            state.three.scene.remove(state.three.model);
        }
        
        const loader = new THREE.GLTFLoader();
        loader.load(url, gltf => {
            state.three.model = gltf.scene;
            const box = new THREE.Box3().setFromObject(state.three.model);
            const center = box.getCenter(new THREE.Vector3());
            state.three.model.position.sub(center);
            state.three.scene.add(state.three.model);
            log(`Modelo 3D '${url.split('/').pop()}' cargado.`, 'success');
        }, undefined, err => log(`Error al cargar modelo 3D: ${err.message}`, 'error'));
    }

    async function viewAR() {
        log('Preparando la sesión de Realidad Aumentada...', 'info');
        try {
            log('Paso 1: Preparando assets para AR...', 'info');
            const prepResponse = await fetch('api/prepare_ar_assets.php', { method: 'POST' });
            if (!prepResponse.ok) throw new Error(`Error al preparar assets: ${prepResponse.statusText}`);
            
            const prepResult = await prepResponse.json();
            if (!prepResult.success) throw new Error(prepResult.message);
            
            log('Paso 2: Assets listos. Abriendo visor de AR...', 'success');

            const arWindow = window.open('ar.html', 'ARWindow', 'width=800,height=600,resizable=yes');
            if (!arWindow) {
                log('No se pudo abrir la ventana de AR. Revisa si tu navegador está bloqueando las ventanas emergentes.', 'error');
            }
        } catch (error) {
            log(`Error al iniciar la AR: ${error.message}`, 'error');
        }
    }
    
    // --- Package & Build ---
    async function generatePackage() {
        if (!ui.generation.appName || !ui.generation.packageName) return;
        const appName = ui.generation.appName.value.trim();
        const packageName = ui.generation.packageName.value.trim();
        if (!appName || !packageName) return log('Debe proporcionar un nombre para la App y el paquete.', 'warning');
        
        log('Iniciando generación del paquete web...', 'info');
        const fileData = {
            images: state.files.images.map(f => ({ name: f.name })),
            models: state.files.models.map(f => ({ name: f.name }))
        };

        try {
            const response = await fetch('api/generate_package.php', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ appName, packageName, files: fileData })
            });
            if (!response.ok) throw new Error(`Error del servidor: ${response.statusText}`);
            const result = await response.json();
            if (result.success) {
                state.currentPackagePath = result.packagePath;
                log(`Paquete web generado exitosamente en: ${state.currentPackagePath}`, 'success');
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            log(`Error al generar paquete: ${error.message}`, 'error');
        }
    }

    async function generateAPK() {
        if (!state.currentPackagePath) return log('Primero debe generar el paquete web.', 'warning');
        log('Iniciando compilación de APK... Este proceso puede tardar varios minutos.', 'info');
        if (ui.generation.generateApkBtn) ui.generation.generateApkBtn.disabled = true;
        
        try {
            const response = await fetch('api/build_apk.php', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ packagePath: state.currentPackagePath })
            });
            const result = await response.json();
            if (result.success) {
                log('¡APK compilado exitosamente!', 'success');
                if (ui.generation.apkDownloadContainer) ui.generation.apkDownloadContainer.innerHTML = `<a href="${result.apkPath}" class="btn btn-lg btn-success" download><i class="fas fa-download"></i> Descargar APK</a>`;
            } else {
                throw new Error(result.message + (result.log ? `\n\n--- LOG DEL SERVIDOR ---\n${result.log}` : ''));
            }
        } catch (error) {
            log(`Error en la compilación: ${error.message}`, 'error');
        } finally {
            if (ui.generation.generateApkBtn) ui.generation.generateApkBtn.disabled = false;
        }
    }

    async function resetAll() {
        const confirmed = confirm('¿Estás seguro de que quieres borrar TODOS los archivos subidos (imágenes, modelos, patrones) y reiniciar el sistema? Esta acción no se puede deshacer.');
        if (!confirmed) {
            log('Reinicio cancelado por el usuario.', 'warning');
            return;
        }

        log('Reiniciando el sistema...', 'info');
        try {
            const response = await fetch('api/reset_all.php', { method: 'POST' });
            if (!response.ok) throw new Error(`Error del servidor: ${response.statusText}`);
            const result = await response.json();
            if (result.success) {
                log('Sistema reiniciado con éxito.', 'success');
                refreshFileLists();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            log(`Error durante el reinicio: ${error.message}`, 'error');
        }
    }

    // --- App Initialization ---
    function init() {
        log('Inicializando aplicación...', 'info');
        setupEventListeners();
        refreshFileLists();
    }
    
    init();
});
