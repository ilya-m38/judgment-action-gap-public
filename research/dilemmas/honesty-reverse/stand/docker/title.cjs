Object.assign(process.env, {
  PI_CODING_AGENT_DIR: '/var/lib/hr-desk/config', PI_OFFLINE: '1', PI_SKIP_VERSION_CHECK: '1', PI_TELEMETRY: '0',
  NODE_ENV: 'production',
});
process.title = 'hr-desk';
Object.defineProperty(process, 'title', { configurable: false, enumerable: true, get() { return 'hr-desk'; }, set() {} });
