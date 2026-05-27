# Guía de Clonado y Configuración para Visual Studio Code

Esta guía contiene los pasos exactos para clonar el repositorio desde la consola de comandos y vincular correctamente las ramas, evitando así el bug visual de sincronización (*tracking*) dentro de la interfaz de Visual Studio Code.

## Prerrequisitos
* Tener Git instalado en el sistema.
* Contar con las credenciales de GitHub ya configuradas en la terminal.

---

## Pasos para la Configuración

### 1. Clonar el repositorio
Abre tu terminal (Git Bash, CMD o PowerShell) en la carpeta donde guardas tus proyectos y ejecuta el siguiente comando para descargar el repositorio con su nombre original:
```bash
git clone https://github.com
```

### 2. Acceder a la carpeta del proyecto
Mueve la línea de comandos *dentro* del directorio que se acaba de crear de forma automática:
```bash
cd Proyecto-Final-Deforestacion-CDMX
```

### 3. Vincular la rama local con la remota (*Bypass* de VS Code)
Para evitar que VS Code falle al hacer *push* o *pull*, fuerza el enlace de seguimiento (*upstream*) ejecutando este comando en la consola:
```bash
git branch --set-upstream-to=origin/main main
```

### 4. Verificar la conexión correcta
Asegúrate de que la rama local está correctamente indexada al servidor remoto con el siguiente comando:
```bash
git branch -vv
```
*Nota: Deberías ver la confirmación `[origin/main]` resaltada al lado del nombre de tu rama.*

### 5. Abrir en Visual Studio Code
Una vez realizados los pasos anteriores, ya puedes abrir el proyecto de forma segura en el editor ejecutando:
```bash
code .
```

---

## Flujo de Trabajo Seguro (Nuevas Ramas)
Si en el futuro creas ramas nuevas y deseas que la interfaz de Visual Studio Code las reconozca al instante sin errores de origen remoto, súbelas la primera vez usando el parámetro `-u`:
```bash
git checkout -b nombre-de-tu-rama
git push -u origin nombre-de-tu-rama
```
