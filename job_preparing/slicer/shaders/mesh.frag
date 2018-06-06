#version 410 core
out vec4 FragColor;

in vec3 norm;
in vec3 FragPos;

uniform vec3 lightColor;
uniform vec3 lightDir;
uniform vec3 objectColor;

void main()
{

    float diff1 = max(dot(norm, lightDir), 0.0);
    vec3 diffuse1 = diff1 * lightColor;
    
    vec3 lightDir2 = vec3(lightDir.x, lightDir.y, -lightDir.z);
    float diff2 = max(dot(norm, lightDir2), 0.0);
    vec3 diffuse2 = diff2 * lightColor;
    
    vec3 result = (diffuse1 + diffuse2) * objectColor;
    FragColor = vec4(result, 1.0);
}