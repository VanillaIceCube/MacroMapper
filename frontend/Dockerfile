# ---- Build stage ----
FROM node:26 AS build

# Set working directory
WORKDIR /frontend

# Copy package.json and package-lock.json and install Node.js dependencies
COPY package*.json ./
RUN npm ci

# Copy your React project code
COPY . .

# Build-time API base URL for Vite
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build optimized React app (outputs to /frontend/dist)
RUN npm run build

# ---- Run stage (Nginx) ----
FROM nginx:alpine

# Nginx serves files from this directory
WORKDIR /usr/share/nginx/html

# SPA-friendly routing (serve index.html for unknown routes)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built static files from the build stage
COPY --from=build /frontend/dist .

# Nginx listens on port 80 inside the container
EXPOSE 80

# Run React server
CMD ["nginx", "-g", "daemon off;"]
