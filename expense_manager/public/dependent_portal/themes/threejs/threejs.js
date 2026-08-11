/**
 * THREE.JS THEME MODULE
 * 3D Data Constellation & Spatial Cyberpunk Interface.
 */

export const ThreejsTheme = {
  name: 'threejs',
  scene: null,
  camera: null,
  renderer: null,
  animFrameId: null,
  resizeHandler: null,
  mouseHandler: null,
  objectsToDispose: [],

  async loadThreeLibrary() {
    if (window.THREE) return window.THREE;
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
      script.onload = () => resolve(window.THREE);
      script.onerror = () => reject(new Error('Failed to load Three.js'));
      document.head.appendChild(script);
    });
  },

  async mount(container, data, utils) {
    const { inr, formatDate } = utils;
    const dependent = data?.dependent || {};
    const pocket_money = data?.pocket_money || data?.balance || {};
    const allowed_categories = data?.allowed_categories || data?.category_breakdown || [];
    const budgets = data?.budgets || [];
    const recent_expenses = data?.recent_expenses || [];
    const trend = data?.trend || [];

    const remaining = pocket_money?.remaining_amount ?? 0;
    const allocated = pocket_money?.allocated_amount ?? 0;
    const spent = pocket_money?.spent_amount ?? 0;
    const carryForward = pocket_money?.carry_forward ?? 0;
    const totalSavings = (dependent?.total_savings || 0) + (remaining > 0 ? remaining : 0);
    const isOverspent = remaining < 0;
    const pctUsed = allocated > 0 ? Math.min(Math.round((spent / (allocated + carryForward)) * 100), 100) : 0;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Create Canvas Element
    let canvas = document.querySelector('#three-bg-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'three-bg-canvas';
      document.body.prepend(canvas);
    }

    container.innerHTML = `
      <div class="three-view">
        <!-- Header -->
        <header class="three-header">
          <div style="display: flex; align-items: center; gap: 14px;">
            <div class="three-avatar">💠</div>
            <div>
              <h1 style="font-size: 22px; font-weight: 700; color: #ffffff; letter-spacing: -0.02em;">${dependent.dependent_name}</h1>
              <p style="font-size: 13px; color: var(--3d-ink-muted);">3D Constellation Financial Portal</p>
            </div>
          </div>
          <div style="padding: 6px 14px; border-radius: 9999px; font-size: 12px; font-weight: 700; background: ${isOverspent ? 'var(--3d-danger-bg)' : 'var(--3d-success-bg)'}; color: ${isOverspent ? 'var(--3d-danger-ink)' : 'var(--3d-success-ink)'}; border: 1px solid ${isOverspent ? 'var(--3d-danger-border)' : 'var(--3d-success-border)'};">
            ${isOverspent ? '● Orbit Alert' : '● Constellation Active'}
          </div>
        </header>

        <!-- Hero Card -->
        <div class="three-hero-card">
          <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 24px;">
            <div>
              <p style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--3d-accent); letter-spacing: 0.08em; margin-bottom: 6px;">
                Financial Core Status
              </p>
              <p class="three-hero-amount ${isOverspent ? 'overspent' : ''}">
                ${inr(remaining)}
              </p>
            </div>
            <div style="padding: 6px 14px; border-radius: 9999px; font-size: 12px; font-weight: 700; background: ${isOverspent ? 'var(--3d-danger-bg)' : 'rgba(56, 189, 248, 0.15)'}; color: ${isOverspent ? 'var(--3d-danger-ink)' : 'var(--3d-accent)'}; border: 1px solid ${isOverspent ? 'var(--3d-danger-border)' : 'var(--3d-border)'};">
              ${isOverspent ? 'Over by ' + inr(Math.abs(remaining)) : `${pctUsed}% Allocated Spend`}
            </div>
          </div>

          <!-- Glowing Progress Bar -->
          <div style="height: 8px; background: rgba(255,255,255,0.06); border-radius: 9999px; overflow: hidden; margin-bottom: 24px;">
            <div style="height: 100%; border-radius: 9999px; width: ${pctUsed}%; background: ${isOverspent ? 'linear-gradient(90deg, #f87171, #ef4444)' : 'linear-gradient(90deg, #38bdf8, #818cf8)'}; box-shadow: 0 0 12px ${isOverspent ? 'rgba(248, 113, 113, 0.6)' : 'rgba(56, 189, 248, 0.6)'};"></div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; border-top: 1px solid var(--3d-border-subtle); padding-top: 20px;">
            <div>
              <p style="font-size: 11px; color: var(--3d-ink-muted); margin-bottom: 4px;">Cycle Allocation</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: #ffffff;">${inr(allocated)}</p>
            </div>
            <div>
              <p style="font-size: 11px; color: var(--3d-ink-muted); margin-bottom: 4px;">Spent</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: #ffffff;">${inr(spent)}</p>
            </div>
            <div>
              <p style="font-size: 11px; color: var(--3d-ink-muted); margin-bottom: 4px;">Rollover Carry-Forward</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: #ffffff;">${inr(carryForward)}</p>
            </div>
            <div>
              <p style="font-size: 11px; color: var(--3d-ink-muted); margin-bottom: 4px;">Total Savings</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: var(--3d-accent); text-shadow: 0 0 10px rgba(56,189,248,0.4);">${inr(totalSavings)}</p>
            </div>
          </div>
        </div>

        <!-- Allowed Categories -->
        <section style="margin-bottom: 32px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
            <div>
              <h2 style="font-size: 18px; font-weight: 700; color: #ffffff;">Allowed Categories</h2>
              <p style="font-size: 12px; color: var(--3d-ink-muted);">Constellation nodes authorized for this dependent</p>
            </div>
            <span style="padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 700; background: rgba(56,189,248,0.15); color: var(--3d-accent); border: 1px solid var(--3d-border);">
              ${allowed_categories.length} Nodes Online
            </span>
          </div>

          <div class="three-grid-3">
            ${allowed_categories.map(cat => `
              <div class="three-cat-card">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                  <span style="font-size: 24px;">${cat.icon || '🏷️'}</span>
                  <span style="font-family: 'Space Grotesk', sans-serif; font-size: 14px; font-weight: 700; color: var(--3d-accent);">
                    ${inr(cat.spent || 0)}
                  </span>
                </div>
                <p style="font-size: 14px; font-weight: 700; color: #ffffff;">${cat.category_name}</p>
                <p style="font-size: 11px; color: var(--3d-ink-muted);">Spent this cycle</p>
              </div>
            `).join('')}
          </div>
        </section>

        <!-- Category Budgets -->
        ${budgets && budgets.length ? `
          <section style="margin-bottom: 32px;">
            <div style="margin-bottom: 16px;">
              <h2 style="font-size: 18px; font-weight: 700; color: #ffffff;">Category Limits</h2>
              <p style="font-size: 12px; color: var(--3d-ink-muted);">Threshold telemetry</p>
            </div>

            <div class="three-table-card">
              ${budgets.map(b => {
                const bPct = b.allocated_amount > 0 ? Math.min(Math.round((b.spent_amount / b.allocated_amount) * 100), 100) : 0;
                return `
                  <div class="three-table-row">
                    <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
                      <span style="font-size: 20px;">${b.category_icon || '🏷️'}</span>
                      <div>
                        <p style="font-size: 14px; font-weight: 700; color: #ffffff;">${b.category_name}</p>
                        <p style="font-size: 11px; color: var(--3d-ink-muted);">${inr(b.spent_amount)} of ${inr(b.allocated_amount)}</p>
                      </div>
                    </div>
                    <div style="width: 140px; margin: 0 16px;">
                      <div style="height: 6px; background: rgba(255,255,255,0.06); border-radius: 9999px; overflow: hidden;">
                        <div style="height: 100%; border-radius: 9999px; width: ${bPct}%; background: ${b.is_overspent ? '#f87171' : '#38bdf8'}; box-shadow: 0 0 8px ${b.is_overspent ? 'rgba(248,113,113,0.5)' : 'rgba(56,189,248,0.5)'};"></div>
                      </div>
                    </div>
                    <span style="padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; background: ${b.is_overspent ? 'var(--3d-danger-bg)' : 'var(--3d-success-bg)'}; color: ${b.is_overspent ? 'var(--3d-danger-ink)' : 'var(--3d-success-ink)'}; border: 1px solid ${b.is_overspent ? 'var(--3d-danger-border)' : 'var(--3d-success-border)'};">
                      ${b.is_overspent ? 'Over budget' : inr(b.remaining_amount) + ' left'}
                    </span>
                  </div>
                `;
              }).join('')}
            </div>
          </section>
        ` : ''}

        <!-- Recent Expenses Feed -->
        <section style="margin-bottom: 32px;">
          <div style="margin-bottom: 16px;">
            <h2 style="font-size: 18px; font-weight: 700; color: #ffffff;">Recent Telemetry</h2>
            <p style="font-size: 12px; color: var(--3d-ink-muted);">Activity ledger</p>
          </div>

          <div class="three-table-card">
            ${recent_expenses.length ? recent_expenses.map(exp => `
              <div class="three-table-row">
                <div style="display: flex; align-items: center; gap: 12px;">
                  <span style="font-size: 20px;">${exp.category_icon || '🏷️'}</span>
                  <div>
                    <p style="font-size: 14px; font-weight: 700; color: #ffffff;">${exp.description || exp.category_name || 'Expense'}</p>
                    <p style="font-size: 11px; color: var(--3d-ink-muted);">${formatDate(exp.expense_date)} · ${exp.category_name}</p>
                  </div>
                </div>
                <p style="font-family: 'Space Grotesk', sans-serif; font-size: 15px; font-weight: 700; color: #ffffff;">${inr(exp.amount)}</p>
              </div>
            `).join('') : `
              <div style="padding: 28px; text-align: center; color: var(--3d-ink-muted); font-size: 14px;">
                No recent transactions recorded.
              </div>
            `}
          </div>
        </section>
      </div>
    `;

    // Initialize Three.js 3D Constellation Scene
    try {
      const THREE = await this.loadThreeLibrary();
      if (!THREE || !canvas) return;

      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
      this.camera.position.z = 30;

      this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

      // Central Financial Core Geometry
      const coreGeo = new THREE.IcosahedronGeometry(isOverspent ? 4.5 : 3.8, 1);
      const coreMat = new THREE.MeshStandardMaterial({
        color: isOverspent ? 0xf43f5e : 0x0284c7,
        emissive: isOverspent ? 0x991b1b : 0x0369a1,
        emissiveIntensity: 0.6,
        wireframe: true,
        transparent: true,
        opacity: 0.85
      });
      const coreMesh = new THREE.Mesh(coreGeo, coreMat);
      this.scene.add(coreMesh);
      this.objectsToDispose.push(coreGeo, coreMat);

      // Category Constellation Satellites
      const satellites = [];
      const catCount = Math.max(allowed_categories.length, 3);
      for (let i = 0; i < catCount; i++) {
        const satGeo = new THREE.OctahedronGeometry(1.2, 0);
        const satMat = new THREE.MeshStandardMaterial({
          color: 0x38bdf8,
          emissive: 0x0284c7,
          wireframe: true
        });
        const satMesh = new THREE.Mesh(satGeo, satMat);
        const angle = (i / catCount) * Math.PI * 2;
        const radius = 12 + (i % 3) * 2;
        satMesh.position.set(Math.cos(angle) * radius, Math.sin(angle) * radius, (Math.sin(i) * 4));
        this.scene.add(satMesh);
        satellites.push({ mesh: satMesh, angle, radius, speed: 0.005 + (i * 0.002) });
        this.objectsToDispose.push(satGeo, satMat);
      }

      // Particle Field
      const particleCount = 400;
      const posArray = new Float32Array(particleCount * 3);
      for (let i = 0; i < particleCount * 3; i++) {
        posArray[i] = (Math.random() - 0.5) * 80;
      }
      const partGeo = new THREE.BufferGeometry();
      partGeo.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
      const partMat = new THREE.PointsMaterial({
        size: 0.15,
        color: isOverspent ? 0xf87171 : 0x38bdf8,
        transparent: true,
        opacity: 0.6
      });
      const particleMesh = new THREE.Points(partGeo, partMat);
      this.scene.add(particleMesh);
      this.objectsToDispose.push(partGeo, partMat);

      // Lighting
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
      const pointLight = new THREE.PointLight(isOverspent ? 0xf43f5e : 0x38bdf8, 2, 50);
      pointLight.position.set(0, 0, 15);
      this.scene.add(ambientLight, pointLight);

      // Mouse Parallax
      let mouseX = 0, mouseY = 0;
      this.mouseHandler = (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 4;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 4;
      };
      window.addEventListener('mousemove', this.mouseHandler, { passive: true });

      // Resize Handler
      this.resizeHandler = () => {
        if (!this.camera || !this.renderer) return;
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
      };
      window.addEventListener('resize', this.resizeHandler);

      // Animation Loop
      const animate = () => {
        if (!this.renderer || !this.scene || !this.camera) return;
        this.animFrameId = requestAnimationFrame(animate);

        if (!reducedMotion) {
          coreMesh.rotation.x += 0.005;
          coreMesh.rotation.y += 0.008;

          satellites.forEach(s => {
            s.angle += s.speed;
            s.mesh.position.x = Math.cos(s.angle) * s.radius;
            s.mesh.position.y = Math.sin(s.angle) * s.radius;
            s.mesh.rotation.x += 0.02;
            s.mesh.rotation.y += 0.02;
          });

          particleMesh.rotation.y -= 0.001;

          this.camera.position.x += (mouseX - this.camera.position.x) * 0.05;
          this.camera.position.y += (-mouseY - this.camera.position.y) * 0.05;
          this.camera.lookAt(0, 0, 0);
        }

        this.renderer.render(this.scene, this.camera);
      };

      animate();
    } catch (e) {
      console.warn('Three.js initialization failed, graceful static fallback:', e);
    }
  },

  unmount() {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler);
      this.resizeHandler = null;
    }
    if (this.mouseHandler) {
      window.removeEventListener('mousemove', this.mouseHandler);
      this.mouseHandler = null;
    }

    this.objectsToDispose.forEach(obj => {
      try { if (obj.dispose) obj.dispose(); } catch (e) {}
    });
    this.objectsToDispose = [];

    if (this.renderer) {
      try {
        this.renderer.forceContextLoss();
        this.renderer.dispose();
      } catch (e) {}
      this.renderer = null;
    }

    const canvas = document.querySelector('#three-bg-canvas');
    if (canvas) canvas.remove();

    this.scene = null;
    this.camera = null;
  }
};
