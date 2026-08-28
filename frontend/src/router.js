import { createRouter, createWebHashHistory } from 'vue-router'
import ImageView from './views/ImageView.vue'
import ListView from './views/ListView.vue'
import ReceiptDetailView from './views/ReceiptDetailView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: ImageView },
    { path: '/list', component: ListView },
    { path: '/receipt/:jobId', component: ReceiptDetailView },
  ],
})
