import { env } from "../config/env";
import type {
  EmotionSocketInboundMessage,
  EmotionSocketOutboundMessage,
} from "../types/emotion";

export interface EmotionSocketOptions {
  onMessage?: (message: EmotionSocketInboundMessage) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
}

export class EmotionSocketClient {
  private socket: WebSocket | null = null;

  constructor(private readonly options: EmotionSocketOptions = {}) {}

  connect(token?: string) {
    if (this.socket && this.socket.readyState < WebSocket.CLOSING) {
      return this.socket;
    }

    this.socket = new WebSocket(`${env.wsBaseUrl}/ws/emotion`);

    this.socket.addEventListener("open", () => {
      this.options.onOpen?.();
      if (token) {
        this.send({ type: "open", access_token: token });
      }
    });

    this.socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data) as EmotionSocketInboundMessage;
      this.options.onMessage?.(payload);
    });

    this.socket.addEventListener("close", (event) => {
      this.options.onClose?.(event);
    });

    this.socket.addEventListener("error", (event) => {
      this.options.onError?.(event);
    });

    return this.socket;
  }

  send(message: EmotionSocketOutboundMessage) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected.");
    }

    this.socket.send(JSON.stringify(message));
  }

  disconnect(code?: number, reason?: string) {
    this.socket?.close(code, reason);
    this.socket = null;
  }
}
