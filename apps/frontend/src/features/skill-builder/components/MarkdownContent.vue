<script setup lang="ts">
import { computed } from "vue";
import { renderMarkdown } from "../lib/builderUi";

const props = defineProps<{ source: string }>();
const html = computed(() => renderMarkdown(props.source));
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -- rendered HTML is sanitized in renderMarkdown. -->
  <div class="builder-markdown" v-html="html" />
</template>
