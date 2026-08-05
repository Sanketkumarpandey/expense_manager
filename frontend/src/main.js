import { createApp } from 'vue'
import { FrappeUI, setConfig, frappeRequest } from 'frappe-ui'
import App from './App.vue'
import router from './router'
import './index.css'

setConfig('resourceFetcher', frappeRequest)

let app = createApp(App)

app.use(router)
app.use(FrappeUI)
app.mount('#app')
