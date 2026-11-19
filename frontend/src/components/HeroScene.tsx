"use client";

/**
 * Three.js hero scene — floating "product" geometry with colourful
 * lighting. Client-only (loaded via next/dynamic with ssr:false) and
 * guarded: if WebGL is unavailable (jsdom, old devices) it renders a
 * static gradient panel instead of crashing.
 */

import { useEffect, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import type { Group } from "three";

function hasWebGL(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return !!(
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl")
    );
  } catch {
    return false;
  }
}

function SpinGroup({ pointer }: { pointer: { x: number; y: number } }) {
  const groupRef = useRef<Group>(null);

  useFrame((state, delta) => {
    const g = groupRef.current;
    if (!g) return;
    g.rotation.y += delta * 0.25;
    // Gentle parallax toward the pointer.
    g.rotation.x += (pointer.y * 0.35 - g.rotation.x) * 0.05;
    g.position.x += (pointer.x * 0.4 - g.position.x) * 0.05;
    state.camera.position.z += (6 - state.camera.position.z) * 0.1;
  });

  return (
    <group ref={groupRef}>
      {/* Central "product box" */}
      <Float speed={1.6} rotationIntensity={0.6} floatIntensity={0.9}>
        <mesh castShadow>
          <boxGeometry args={[1.5, 1.5, 1.5]} />
          <meshStandardMaterial color="#4f8cff" metalness={0.35} roughness={0.25} />
        </mesh>
        <mesh scale={1.02}>
          <boxGeometry args={[1.5, 1.5, 1.5]} />
          <meshBasicMaterial color="#22d3ee" wireframe transparent opacity={0.35} />
        </mesh>
      </Float>

      {/* Orbiting accents */}
      <Float speed={2.2} rotationIntensity={1.2} floatIntensity={1.4}>
        <mesh position={[2.4, 1.1, -0.6]}>
          <icosahedronGeometry args={[0.55, 0]} />
          <meshStandardMaterial color="#a78bfa" metalness={0.5} roughness={0.2} />
        </mesh>
      </Float>
      <Float speed={1.9} rotationIntensity={1} floatIntensity={1.1}>
        <mesh position={[-2.5, -0.9, 0.4]}>
          <torusGeometry args={[0.5, 0.2, 24, 64]} />
          <meshStandardMaterial color="#f472b6" metalness={0.45} roughness={0.3} />
        </mesh>
      </Float>
      <Float speed={2.5} rotationIntensity={1.4} floatIntensity={1.6}>
        <mesh position={[1.9, -1.4, 0.8]}>
          <sphereGeometry args={[0.45, 32, 32]} />
          <meshStandardMaterial color="#34d399" metalness={0.4} roughness={0.25} />
        </mesh>
      </Float>
      <Float speed={1.4} rotationIntensity={0.8} floatIntensity={1.2}>
        <mesh position={[-1.8, 1.6, -0.8]}>
          <coneGeometry args={[0.45, 0.9, 4]} />
          <meshStandardMaterial color="#fbbf24" metalness={0.5} roughness={0.3} />
        </mesh>
      </Float>
    </group>
  );
}

export default function HeroScene() {
  const [supported, setSupported] = useState(false);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });

  useEffect(() => {
    let alive = true;
    // Deferred one tick so the first client render matches the server's
    // fallback tree (hydration-safe), then we upgrade to the live canvas.
    const boot = window.setTimeout(() => {
      if (alive) setSupported(hasWebGL());
    }, 0);
    const onMove = (e: MouseEvent) => {
      setPointer({
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: -((e.clientY / window.innerHeight) * 2 - 1),
      });
    };
    window.addEventListener("mousemove", onMove);
    return () => {
      alive = false;
      window.clearTimeout(boot);
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

  if (!supported) {
    // Graceful fallback (tests, no-WebGL devices): static gradient panel.
    return (
      <div
        className="flex h-full w-full items-center justify-center rounded-2xl border border-border bg-gradient-to-br from-accent/30 via-accent-2/20 to-[#a78bfa]/30"
        aria-hidden
        data-testid="hero-scene-fallback"
      >
        <span className="text-gradient text-5xl font-black tracking-tighter">3D</span>
      </div>
    );
  }

  return (
    <div className="h-full w-full" data-testid="hero-scene">
      <Canvas
        camera={{ position: [0, 0, 6], fov: 45 }}
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.55} />
        <directionalLight position={[5, 5, 5]} intensity={1.1} color="#ffffff" />
        <pointLight position={[-6, -3, 2]} intensity={2.2} color="#22d3ee" />
        <pointLight position={[6, 4, -2]} intensity={2} color="#a78bfa" />
        <SpinGroup pointer={pointer} />
      </Canvas>
    </div>
  );
}
