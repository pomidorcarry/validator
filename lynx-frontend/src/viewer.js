import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { IfcLoader } from 'three-ifc';

let scene, camera, renderer, controls;
let ifcModel = null;

export function initScene(container) {
    if (renderer) {
        renderer.dispose();
    }
    
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);
    
    camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 10000);
    camera.position.set(50, 50, 50);
    
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);
    
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    
    const light = new THREE.DirectionalLight(0xffffff);
    light.position.set(100, 100, 100);
    scene.add(light);
    
    const ambient = new THREE.AmbientLight(0x404040);
    scene.add(ambient);
    
    const grid = new THREE.GridHelper(100, 50, 0x10b981, 0x2a2a2a);
    scene.add(grid);
    
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();
    
    window.addEventListener('resize', () => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });
    
    console.log('3D scene initialized');
}

export async function loadIfcFromBuffer(buffer) {
    if (!scene) {
        const container = document.getElementById('viewer-container');
        initScene(container);
    }
    
    console.log('Loading IFC from buffer, size:', buffer.byteLength);
    
    try {
        const model = await IfcLoader.load(buffer);
        const group = model.group.threeJsInstance;
        
        if (ifcModel) {
            scene.remove(ifcModel.group.threeJsInstance);
        }
        
        scene.add(group);
        ifcModel = model;
        
        const box = new THREE.Box3().setFromObject(group);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z) * 1.5;
        
        camera.position.set(center.x + maxDim, center.y + maxDim, center.z + maxDim);
        camera.lookAt(center);
        controls.target.copy(center);
        
        console.log('Model loaded successfully');
        return model;
        
    } catch (e) {
        console.error('IFC parse error:', e);
        throw e;
    }
}