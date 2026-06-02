from flask import Flask, render_template, Response
import cv2

app = Flask(__name__)

def generar_frames():
    camara = cv2.VideoCapture(0)
    
    # --- INICIO DE OPTIMIZACIONES ---
    # 1. Le decimos a la cámara que solo guarde 1 frame en cola (elimina el retraso acumulado)
    camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    # 2. Forzamos una resolución más pequeña (640x480)
    camara.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # --- FIN DE OPTIMIZACIONES ---
    
    while True:
        exito, frame = camara.read()
        if not exito:
            break
        else:
            # 3. Comprimimos el JPEG al 80% de calidad para que pese menos en la red
            parametros_jpg = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode('.jpg', frame, parametros_jpg)
            
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Usar threaded=True ayuda a que Flask maneje mejor el flujo de datos
    app.run(host='0.0.0.0', port=5000, threaded=True)