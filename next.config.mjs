/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Next 16's CLI checker cannot reliably parse `tsc --showConfig` under
  // constrained build environments. The TypeScript API checker performs the
  // same validation without spawning that CLI subprocess.
  experimental: {
    useTypeScriptCli: false,
  },
};

export default nextConfig;
