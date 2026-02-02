<!--
   - verinice.veo web
   - Copyright (C) 2022  Jonas Heitmann
   - 
   - This program is free software: you can redistribute it and/or modify
   - it under the terms of the GNU Affero General Public License as published by
   - the Free Software Foundation, either version 3 of the License, or
   - (at your option) any later version.
   - 
   - This program is distributed in the hope that it will be useful,
   - but WITHOUT ANY WARRANTY; without even the implied warranty of
   - MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   - GNU Affero General Public License for more details.
   - 
   - You should have received a copy of the GNU Affero General Public License
   - along with this program.  If not, see <http://www.gnu.org/licenses/>.
-->
<template>
  <div class="logo-container">
    <img 
      src="/logo.png" 
      alt="SparksBM Logo" 
      class="logo-image"
    />
    <svg viewBox="0 0 120 30" version="1.1" xmlns="http://www.w3.org/2000/svg" class="logo-text" v-bind="$attrs">
    <text
        x="0"
      y="50%"
      font-family="Arial, sans-serif"
      font-size="20"
      font-weight="bold"
      fill="#E53935"
        text-anchor="start"
      dominant-baseline="middle"
    >
      SparksBM
    </text>
  </svg>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped lang="scss">
.logo-container {
  display: flex;
  align-items: center;
  gap: 0;
  background: transparent;
}

.logo-image {
  height: 24px;
  width: auto;
  object-fit: contain;
  background: transparent;
}

.logo-text {
  height: 24px;
  width: auto;
  background: transparent;
}
</style>
