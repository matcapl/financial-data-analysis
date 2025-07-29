.PHONY: db api client all

db:
	@echo "Creating role & db"
	-sudo -u postgres psql -c "CREATE ROLE a WITH LOGIN PASSWORD 'change_me' SUPERUSER;"
	-sudo -u postgres psql -c "CREATE DATABASE finance OWNER a;"
	psql -U a -d finance -f schema/question_templates.sql

api:
	cd server && npm install && npm run dev

client:
	cd client && npm install && npm start

all: db
	@echo "Open two extra terminals and run 'make api' and 'make client'"
