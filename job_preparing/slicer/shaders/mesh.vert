#version 410 core
layout (location = 0) in vec3 v;
layout (location = 1) in vec3 n;

uniform mat4 model;
uniform mat4 view;

out vec3 norm;
out vec3 FragPos;

void main() {
    gl_Position = view * model * vec4(v, 1);
    gl_Position.w = (gl_Position.z + 1.0);
    
    norm = normalize(n);
    FragPos = vec3(model * vec4(v, 1.0));
}