import { useEffect, useRef, useCallback } from 'react';
import { useRealtimeStore } from '../../stores/realtime.store';
import { apiService } from '../api/apiService';

interface UseWebSocketOptions {
  onMessage?: (message: any) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
  autoConnect?: boolean;
}

export const useWebSocket = (options: UseWebSocketOptions = {}) => {
  const { onMessage, onError, onClose, autoConnect = true } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const { setWsConnected, addEmojiReaction, addNotification } = useRealtimeStore();

  const connect = useCallback(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.warn('[WebSocket] No access token available');
      return;
    }

    const handleMessage = (message: any) => {
      // Handle emoji reactions
      if (message.type === 'emoji' || message.type === 'poke') {
        const { from_user_id, emoji, to_user_id } = message.payload || message;
        if (to_user_id && emoji) {
          addEmojiReaction(to_user_id, emoji, from_user_id);
        }
      }

      // Handle notifications
      if (message.type === 'notification') {
        addNotification({
          id: `notif-${Date.now()}`,
          type: 'system',
          message: message.payload?.message || 'New notification',
          timestamp: Date.now(),
          read: false,
        });
      }

      // Call custom handler
      onMessage?.(message);
    };

    const handleError = (error: Event) => {
      console.error('[WebSocket] Error:', error);
      setWsConnected(false);
      onError?.(error);
    };

    const handleClose = () => {
      console.log('[WebSocket] Connection closed');
      setWsConnected(false);
      onClose?.();
    };

    wsRef.current = apiService.connectWebSocket(
      token,
      handleMessage,
      handleError,
      handleClose
    );

    if (wsRef.current) {
      setWsConnected(true);
    }
  }, [onMessage, onError, onClose, addEmojiReaction, addNotification, setWsConnected]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setWsConnected(false);
    }
  }, [setWsConnected]);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    connect,
    disconnect,
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
  };
};
