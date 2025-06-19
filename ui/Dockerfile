FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application
COPY . .

# Set build-time argument
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

# Build the application
RUN npm run build

# Expose the port
EXPOSE 8080

# Command to run the application
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"] 