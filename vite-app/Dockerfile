FROM node:20-alpine
WORKDIR /app
COPY package.json yarn.lock* ./
RUN yarn install
COPY . .
EXPOSE 8086
CMD ["yarn", "dev"]
