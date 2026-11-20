/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  compress: true,
  experimental: {
    // Tree-shake barrel imports so each page ships only the icons/components it uses.
    optimizePackageImports: ["lucide-react", "framer-motion", "recharts", "date-fns"],
  },
};
export default nextConfig;
