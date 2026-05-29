FROM node:25.6.1-alpine

WORKDIR /app

RUN apk add curl

# Copy package files (package-lock.json is committed for reproducible installs)
COPY package*.json ./

# Install dependencies reproducibly from the committed lockfile.
# npm ci fails loudly if package.json and package-lock.json drift,
# surfacing missing deps at build time instead of at runtime.
RUN npm ci

# Copy the rest of the application
COPY . .

# Set build-time argument
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

# Expose the port
EXPOSE 8080

# Command to run the application
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"] 
