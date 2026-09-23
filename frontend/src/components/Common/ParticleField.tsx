import { useEffect, useRef } from "react"

import { cn } from "@/lib/utils"

export function ParticleField({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (
      !canvas ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return
    const context = canvas.getContext("2d")
    if (!context) return
    let frame = 0
    let width = 0
    let height = 0
    let pointerX = 0.72
    let pointerY = 0.24
    const particles = Array.from({ length: 72 }, () => ({
      x: Math.random(),
      y: Math.random(),
      depth: 0.25 + Math.random() * 0.75,
      vx: (Math.random() - 0.5) * 0.00018,
      vy: (Math.random() - 0.5) * 0.00018,
    }))
    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      width = rect.width
      height = rect.height
      canvas.width = Math.round(width * devicePixelRatio)
      canvas.height = Math.round(height * devicePixelRatio)
      context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0)
    }
    const onPointerMove = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect()
      pointerX = (event.clientX - rect.left) / rect.width
      pointerY = (event.clientY - rect.top) / rect.height
    }
    const draw = () => {
      context.clearRect(0, 0, width, height)
      for (const particle of particles) {
        const dx = pointerX - particle.x
        const dy = pointerY - particle.y
        const distance = Math.max(0.08, Math.hypot(dx, dy))
        particle.vx += (dx / distance) * 0.0000025
        particle.vy += (dy / distance) * 0.0000025
        particle.vx *= 0.994
        particle.vy *= 0.994
        particle.x = (particle.x + particle.vx + 1) % 1
        particle.y = (particle.y + particle.vy + 1) % 1
        context.beginPath()
        context.fillStyle = `rgba(255,255,255,${0.12 + particle.depth * 0.5})`
        context.arc(
          particle.x * width,
          particle.y * height,
          particle.depth * 1.45,
          0,
          Math.PI * 2,
        )
        context.fill()
      }
      frame = requestAnimationFrame(draw)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(canvas)
    canvas.addEventListener("pointermove", onPointerMove)
    resize()
    draw()
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      canvas.removeEventListener("pointermove", onPointerMove)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className={cn(
        "pointer-events-auto absolute inset-0 h-full w-full",
        className,
      )}
    />
  )
}
