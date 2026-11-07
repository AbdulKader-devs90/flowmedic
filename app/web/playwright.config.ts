import { defineConfig } from '@playwright/test'
export default defineConfig({ testDir:'./e2e',fullyParallel:false,workers:1,timeout:20000,reporter:'list',outputDir:'../../.cache/ui-test-results',use:{ baseURL:'http://127.0.0.1:5173',viewport:{ width:1440,height:1000 },launchOptions:{ channel:'chrome' },trace:'retain-on-failure' } })
