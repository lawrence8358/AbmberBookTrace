<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import AppIcon from "./AppIcon.vue";

defineProps<{ src: string }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
const stage = ref<HTMLElement | null>(null);
const scale = ref(1);
const x = ref(0);
const y = ref(0);
const failed = ref(false);
const pointers = new Map<number, { x: number; y: number }>();
let previousOverflow = "";
onMounted(() => {
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  dialog.value?.showModal();
});
onBeforeUnmount(() => { dialog.value?.close(); document.body.style.overflow = previousOverflow; });

function reset() { scale.value = 1; x.value = 0; y.value = 0; }
function zoom(next: number, anchorX = 0, anchorY = 0) {
  const clamped = Math.min(5, Math.max(1, next));
  const ratio = clamped / scale.value;
  x.value = anchorX - (anchorX - x.value) * ratio;
  y.value = anchorY - (anchorY - y.value) * ratio;
  scale.value = clamped;
  if (clamped === 1) reset();
  constrain();
}
function constrain() {
  const bounds = stage.value?.getBoundingClientRect();
  if (!bounds) return;
  const maxX = bounds.width * (scale.value - 1) / 2;
  const maxY = bounds.height * (scale.value - 1) / 2;
  x.value = Math.max(-maxX, Math.min(maxX, x.value));
  y.value = Math.max(-maxY, Math.min(maxY, y.value));
}
function down(event: PointerEvent) {
  if (event.pointerType === "mouse" && event.button !== 0) return;
  stage.value?.setPointerCapture(event.pointerId);
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
}
function move(event: PointerEvent) {
  const before = pointers.get(event.pointerId);
  if (!before) return;
  const old = [...pointers.values()];
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
  const current = [...pointers.values()];
  if (current.length === 2) {
    const a = old[0]!, b = old[1]!, c = current[0]!, d = current[1]!;
    const distance = Math.hypot(a.x - b.x, a.y - b.y);
    const bounds = stage.value?.getBoundingClientRect();
    if (distance && bounds) {
      zoom(scale.value * Math.hypot(c.x - d.x, c.y - d.y) / distance,
        (a.x + b.x) / 2 - bounds.left - bounds.width / 2,
        (a.y + b.y) / 2 - bounds.top - bounds.height / 2);
      x.value += (c.x + d.x - a.x - b.x) / 2;
      y.value += (c.y + d.y - a.y - b.y) / 2;
    }
  } else if (current.length === 1 && scale.value > 1) {
    x.value += event.clientX - before.x;
    y.value += event.clientY - before.y;
  }
  constrain();
}
function handleKey(event: KeyboardEvent) {
  if (event.key === "+" || event.key === "=") { event.preventDefault(); zoom(scale.value * 1.5); }
  if (event.key === "-") { event.preventDefault(); zoom(scale.value / 1.5); }
  if (event.key === "0") reset();
}
function up(event: PointerEvent) { pointers.delete(event.pointerId); }
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="cover-viewer" aria-label="全螢幕封面" aria-describedby="cover-viewer-help" @keydown="handleKey" @cancel.prevent="emit('close')">
      <button autofocus class="cover-viewer-close" type="button" aria-label="關閉封面檢視" @click="emit('close')"><AppIcon name="close" /></button>
      <p id="cover-viewer-help" class="sr-only">雙指縮放、放大後拖曳。滑鼠可滾輪縮放或雙擊；鍵盤加減鍵縮放，0 重設，Esc 關閉。</p>
      <div ref="stage" class="cover-viewer-stage" :class="{ 'is-zoomed': scale > 1 }"
        @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up" @lostpointercapture="up"
        @dblclick="scale > 1 ? reset() : zoom(2)" @wheel.prevent="zoom(scale * ( $event.deltaY < 0 ? 1.15 : 1 / 1.15))">
        <p v-if="failed" role="alert">無法載入封面，請關閉後重新開啟。</p>
        <img v-else :src="src" alt="完整書籍封面" draggable="false" :style="{ transform: `translate(${x}px, ${y}px) scale(${scale})` }" @error="failed = true" />
      </div>

    </dialog>
  </Teleport>
</template>
