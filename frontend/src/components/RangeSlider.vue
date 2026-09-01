<script setup>
import { computed } from 'vue'

const props = defineProps({
  min: { type: Number, required: true },
  max: { type: Number, required: true },
  modelValue: { type: Array, required: true }, // [startMs, endMs]
  step: { type: Number, default: 86_400_000 },
})
const emit = defineEmits(['update:modelValue'])

const range = computed(() => Math.max(props.max - props.min, 1))

const fillStyle = computed(() => {
  const l = ((props.modelValue[0] - props.min) / range.value) * 100
  const r = ((props.modelValue[1] - props.min) / range.value) * 100
  return { left: `${l}%`, width: `${Math.max(r - l, 0)}%` }
})

function onMin(e) {
  const v = Math.min(Number(e.target.value), props.modelValue[1])
  emit('update:modelValue', [v, props.modelValue[1]])
}

function onMax(e) {
  const v = Math.max(Number(e.target.value), props.modelValue[0])
  emit('update:modelValue', [props.modelValue[0], v])
}
</script>

<template>
  <div class="rs">
    <div class="rs-track">
      <div class="rs-fill" :style="fillStyle" />
    </div>
    <input
      type="range"
      class="rs-thumb"
      :min="min" :max="max" :step="step"
      :value="modelValue[0]"
      @input="onMin"
    />
    <input
      type="range"
      class="rs-thumb"
      :min="min" :max="max" :step="step"
      :value="modelValue[1]"
      @input="onMax"
    />
  </div>
</template>

<style scoped>
.rs {
  position: relative;
  height: 6px;
  margin: 10px 0;
}

.rs-track {
  position: absolute;
  inset: 0;
  background: #ddd;
  border-radius: 3px;
}

.rs-fill {
  position: absolute;
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
}

.rs-thumb {
  position: absolute;
  width: 100%;
  top: -7px;
  height: 20px;
  margin: 0;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  pointer-events: none;
}

.rs-thumb::-webkit-slider-runnable-track {
  background: transparent;
}

.rs-thumb::-moz-range-track {
  background: transparent;
}

.rs-thumb::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
  pointer-events: all;
  cursor: pointer;
}

.rs-thumb::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
  pointer-events: all;
  cursor: pointer;
}
</style>
