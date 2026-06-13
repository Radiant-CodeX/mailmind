'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';

/**
 * Animated "neural mail-stream": a particle ribbon orbiting a wireframe core,
 * with a squadron of glowing paper planes flying through it.
 * Mouse parallax + scroll-reactive camera. Pure three.js to keep bundle lean.
 */
export function HeroCanvas() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x05060a, 0.05);

    const camera = new THREE.PerspectiveCamera(
      60,
      mount.clientWidth / mount.clientHeight,
      0.1,
      100,
    );
    camera.position.set(0, 0, 16);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    // ── Particle ribbon ──────────────────────────────────────────────
    const COUNT = 9000;
    const positions = new Float32Array(COUNT * 3);
    const colors = new Float32Array(COUNT * 3);
    const seeds = new Float32Array(COUNT);

    const colorA = new THREE.Color('#6366f1');
    const colorB = new THREE.Color('#a855f7');
    const colorC = new THREE.Color('#22d3ee');

    for (let i = 0; i < COUNT; i++) {
      const t = (i / COUNT) * Math.PI * 2;
      const radius = 6 + Math.sin(t * 3) * 1.6;
      const spread = (Math.random() - 0.5) * 2.4;
      positions[i * 3] = Math.cos(t * 2) * radius + spread;
      positions[i * 3 + 1] = Math.sin(t * 3) * 2.4 + spread * 0.7;
      positions[i * 3 + 2] = Math.sin(t * 2) * radius * 0.6 + spread;
      seeds[i] = Math.random();

      const mix = Math.random();
      const c =
        mix < 0.65
          ? colorA.clone().lerp(colorB, Math.random())
          : colorB.clone().lerp(colorC, Math.random());
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 0.045,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    const points = new THREE.Points(geometry, material);
    points.rotation.x = -0.35;
    scene.add(points);

    // ── Wireframe core ───────────────────────────────────────────────
    const coreGeo = new THREE.IcosahedronGeometry(1.4, 3);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0x6366f1,
      wireframe: true,
      transparent: true,
      opacity: 0.08,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    scene.add(core);

    // Second outer shell rotating opposite for depth
    const shellGeo = new THREE.IcosahedronGeometry(2.6, 1);
    const shellMat = new THREE.MeshBasicMaterial({
      color: 0x22d3ee,
      wireframe: true,
      transparent: true,
      opacity: 0.04,
    });
    const shell = new THREE.Mesh(shellGeo, shellMat);
    scene.add(shell);

    // ── Paper planes (glowing darts orbiting through the stream) ────
    const PLANES = 14;
    const planeGroup = new THREE.Group();
    scene.add(planeGroup);

    // dart shape: flattened tetrahedron-ish cone
    const dartGeo = new THREE.ConeGeometry(0.16, 0.55, 4);
    dartGeo.rotateX(Math.PI / 2); // point forward along +Z
    dartGeo.scale(1, 0.35, 1); // flatten like a paper plane

    const planeData: {
      mesh: THREE.Mesh;
      trail: THREE.Mesh;
      radius: number;
      speed: number;
      phase: number;
      tilt: number;
      yAmp: number;
    }[] = [];

    const trailGeo = new THREE.PlaneGeometry(0.04, 1.1);
    trailGeo.translate(0, 0, -0.75);

    for (let i = 0; i < PLANES; i++) {
      const hue = Math.random();
      const col =
        hue < 0.5 ? 0x818cf8 : hue < 0.8 ? 0xc084fc : 0x67e8f9;

      const mat = new THREE.MeshBasicMaterial({
        color: col,
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(dartGeo, mat);

      const trailMat = new THREE.MeshBasicMaterial({
        color: col,
        transparent: true,
        opacity: 0.22,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      });
      const trail = new THREE.Mesh(trailGeo, trailMat);
      mesh.add(trail);

      planeGroup.add(mesh);
      planeData.push({
        mesh,
        trail,
        radius: 4.5 + Math.random() * 5.5,
        speed: 0.12 + Math.random() * 0.22,
        phase: Math.random() * Math.PI * 2,
        tilt: (Math.random() - 0.5) * 1.4,
        yAmp: 0.8 + Math.random() * 2.0,
      });
    }

    // ── Mouse parallax + scroll reactivity ──────────────────────────
    const target = { x: 0, y: 0 };
    const onPointerMove = (e: PointerEvent) => {
      target.x = (e.clientX / window.innerWidth - 0.5) * 0.6;
      target.y = (e.clientY / window.innerHeight - 0.5) * 0.4;
    };
    window.addEventListener('pointermove', onPointerMove);

    let scrollFactor = 0;
    const onScroll = () => {
      scrollFactor = Math.min(window.scrollY / window.innerHeight, 1.5);
    };
    window.addEventListener('scroll', onScroll, { passive: true });

    const onResize = () => {
      if (!mount) return;
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener('resize', onResize);

    // ── Animation loop ───────────────────────────────────────────────
    const basePositions = positions.slice();
    const clock = new THREE.Clock();
    const prevPos = new THREE.Vector3();
    const nextPos = new THREE.Vector3();
    let raf = 0;

    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      points.rotation.y = t * 0.05 + scrollFactor * 0.6;
      points.rotation.x = -0.35 + scrollFactor * 0.25;
      core.rotation.y = -t * 0.12;
      core.rotation.x = t * 0.08;
      shell.rotation.y = t * 0.06;
      shell.rotation.z = -t * 0.04;

      // breathing ribbon
      const pos = geometry.attributes.position.array as Float32Array;
      for (let i = 0; i < COUNT; i++) {
        const s = seeds[i];
        pos[i * 3 + 1] =
          basePositions[i * 3 + 1] + Math.sin(t * (0.6 + s * 0.5) + s * 12) * 0.35;
      }
      geometry.attributes.position.needsUpdate = true;

      // fly the planes along tilted orbits, nose pointing at velocity
      for (const p of planeData) {
        const a = t * p.speed + p.phase;
        const aN = a + 0.02;

        prevPos.set(
          Math.cos(a) * p.radius,
          Math.sin(a * 1.7) * p.yAmp + Math.sin(a) * p.tilt * 2,
          Math.sin(a) * p.radius * 0.7,
        );
        nextPos.set(
          Math.cos(aN) * p.radius,
          Math.sin(aN * 1.7) * p.yAmp + Math.sin(aN) * p.tilt * 2,
          Math.sin(aN) * p.radius * 0.7,
        );

        p.mesh.position.copy(prevPos);
        p.mesh.lookAt(nextPos);
        // bank into the turn
        p.mesh.rotateZ(Math.sin(a * 2) * 0.5);
      }

      // camera: mouse ease + scroll dolly-back
      camera.position.x += (target.x * 4 - camera.position.x) * 0.04;
      camera.position.y += (-target.y * 3 - camera.position.y) * 0.04;
      camera.position.z = 16 + scrollFactor * 6;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onResize);
      geometry.dispose();
      material.dispose();
      coreGeo.dispose();
      coreMat.dispose();
      shellGeo.dispose();
      shellMat.dispose();
      dartGeo.dispose();
      trailGeo.dispose();
      planeData.forEach((p) => {
        (p.mesh.material as THREE.Material).dispose();
        (p.trail.material as THREE.Material).dispose();
      });
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} className="absolute inset-0" aria-hidden="true" />;
}
