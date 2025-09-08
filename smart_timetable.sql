CREATE DATABASE smart_timetable;
CREATE USER 'username'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON smart_timetable.* TO 'username'@'localhost';
FLUSH PRIVILEGES;
