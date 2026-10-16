/**
 * Victoria AI - 3D Neural Holographic Core (Three.js)
 * Interactive rotating neural particle cloud with state-reactive pulsation.
 */

class NeuralBrainCore {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.particles = null;
        this.wireCore = null;
        this.rings = [];
        this.state = 'IDLE'; // IDLE, THINKING, SPEAKING, REA_ACTIVE
        this.intensity = 1.0;
        this.clock = new THREE.Clock();

        this.init();
        this.animate();
    }

    init() {
        const width = this.container.clientWidth || 300;
        const height = this.container.clientHeight || 240;

        // Scene
        this.scene = new THREE.Scene();

        // Camera
        this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
        this.camera.position.z = 18;

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);

        // 1. Neural Particle Sphere
        const particleCount = 1200;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);

        const colorCyan = new THREE.Color(0x00f0ff);
        const colorPurple = new THREE.Color(0xa855f7);

        for (let i = 0; i < particleCount; i++) {
            const u = Math.random();
            const v = Math.random();
            const theta = u * 2.0 * Math.PI;
            const phi = Math.acos(2.0 * v - 1.0);
            const r = 7.5 + (Math.random() - 0.5) * 1.5;

            const x = r * Math.sin(phi) * Math.cos(theta);
            const y = r * Math.sin(phi) * Math.sin(theta);
            const z = r * Math.cos(phi);

            positions[i * 3] = x;
            positions[i * 3 + 1] = y;
            positions[i * 3 + 2] = z;

            const mixedColor = colorCyan.clone().lerp(colorPurple, Math.random());
            colors[i * 3] = mixedColor.r;
            colors[i * 3 + 1] = mixedColor.g;
            colors[i * 3 + 2] = mixedColor.b;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const material = new THREE.PointsMaterial({
            size: 0.28,
            vertexColors: true,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending,
        });

        this.particles = new THREE.Points(geometry, material);
        this.scene.add(this.particles);

        // 2. Wireframe Inner Geometric Core
        const coreGeo = new THREE.IcosahedronGeometry(4.5, 2);
        const coreMat = new THREE.MeshBasicMaterial({
            color: 0x00f0ff,
            wireframe: true,
            transparent: true,
            opacity: 0.25,
        });
        this.wireCore = new THREE.Mesh(coreGeo, coreMat);
        this.scene.add(this.wireCore);

        // 3. Orbital Scanner Rings (REA Hologram)
        for (let r = 0; r < 2; r++) {
            const ringGeo = new THREE.TorusGeometry(9.0 + r * 1.5, 0.04, 8, 80);
            const ringMat = new THREE.MeshBasicMaterial({
                color: r === 0 ? 0x00f0ff : 0xa855f7,
                transparent: true,
                opacity: 0.4,
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / (3 + r * 2);
            ring.rotation.y = Math.PI / (4 + r);
            this.rings.push(ring);
            this.scene.add(ring);
        }

        // Mouse Drag Interaction
        let isDragging = false;
        let prevMouse = { x: 0, y: 0 };

        this.container.addEventListener('mousedown', (e) => {
            isDragging = true;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mouseup', () => isDragging = false);

        this.container.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaX = e.clientX - prevMouse.x;
            const deltaY = e.clientY - prevMouse.y;
            this.particles.rotation.y += deltaX * 0.008;
            this.particles.rotation.x += deltaY * 0.008;
            this.wireCore.rotation.y += deltaX * 0.008;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        // Resize handler
        window.addEventListener('resize', () => this.onResize());
    }

    onResize() {
        if (!this.container || !this.renderer || !this.camera) return;
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    setState(newState) {
        this.state = newState.toUpperCase();
        const badge = document.getElementById('neuralState');
        if (badge) {
            badge.textContent = this.state;
            if (this.state === 'THINKING' || this.state === 'REA_ACTIVE') {
                badge.style.borderColor = 'var(--neon-purple)';
                badge.style.color = 'var(--neon-purple)';
            } else if (this.state === 'SPEAKING') {
                badge.style.borderColor = 'var(--neon-green)';
                badge.style.color = 'var(--neon-green)';
            } else {
                badge.style.borderColor = 'var(--neon-cyan)';
                badge.style.color = 'var(--neon-cyan)';
            }
        }
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        const elapsed = this.clock.getElapsedTime();
        let speedMult = 1.0;
        let pulseMult = 1.0;

        if (this.state === 'THINKING' || this.state === 'REA_ACTIVE') {
            speedMult = 3.5;
            pulseMult = 1.4;
        } else if (this.state === 'SPEAKING') {
            speedMult = 2.0;
            pulseMult = 1.25;
        }

        // Particle cloud rotation
        if (this.particles) {
            this.particles.rotation.y += 0.004 * speedMult;
            this.particles.rotation.x = Math.sin(elapsed * 0.5) * 0.15;

            // Breathing pulse effect
            const scale = 1.0 + Math.sin(elapsed * 3.0 * pulseMult) * 0.06;
            this.particles.scale.set(scale, scale, scale);
        }

        // Inner core rotation
        if (this.wireCore) {
            this.wireCore.rotation.y -= 0.007 * speedMult;
            this.wireCore.rotation.z += 0.003 * speedMult;
            const coreScale = 1.0 + Math.cos(elapsed * 2.5 * pulseMult) * 0.08;
            this.wireCore.scale.set(coreScale, coreScale, coreScale);
        }

        // Orbital rings
        this.rings.forEach((ring, index) => {
            ring.rotation.z += (index === 0 ? 0.01 : -0.012) * speedMult;
        });

        this.renderer.render(this.scene, this.camera);
    }
}

// Global instance
window.neuralBrain = null;
window.addEventListener('DOMContentLoaded', () => {
    window.neuralBrain = new NeuralBrainCore('threeBrainContainer');
});
