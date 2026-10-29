<script setup>
// Rotation and neighbours of a crop in its space, warnings first.
defineProps({ notes: { type: Array, required: true } });
</script>

<template>
  <ul class="placement-notes">
    <li v-for="note in notes" :key="note.text" :class="note.kind">
      <span class="mark" aria-hidden="true">{{ note.kind === "companion" ? "✓" : "!" }}</span>
      <RouterLink v-if="note.planting_id" :to="`/plantings/${note.planting_id}`">
        {{ note.text }}
      </RouterLink>
      <span v-else>{{ note.text }}</span>
    </li>
  </ul>
</template>

<style scoped>
.placement-notes {
  list-style: none;
  margin: 0;
  padding: 0;
}

li {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 4px 0;
}

li a {
  color: inherit;
  text-decoration: none;
}

.mark {
  flex: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  color: #fff;
  background: var(--hs-warning);
}

.companion .mark {
  background: var(--hs-primary);
}
</style>
