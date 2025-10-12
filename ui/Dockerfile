FROM node:20-alpine

WORKDIR /app

RUN apk add curl

# Copy package files
COPY package*.json ./

RUN rm -rf node_modules package-lock.json
# Install dependencies
RUN npm install

# Copy the rest of the application
COPY . .

# Set build-time argument
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

# Expose the port
EXPOSE 8080

# Command to run the application
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"] 