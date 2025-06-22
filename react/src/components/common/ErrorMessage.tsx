import React from 'react';

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

const ErrorMessage = React.memo(({ message, onRetry, className = '' }: ErrorMessageProps) => {
  return (
    <div className={`row justify-content-center ${className}`} data-testid="error">
      <div className="col-11 text-end">
        <div className="alert alert-danger d-flex align-items-center" role="alert">
          <div className="flex-grow-1">{message}</div>
          {onRetry && (
            <button
              className="btn btn-outline-danger btn-sm ms-2"
              onClick={onRetry}
            >
              再試行
            </button>
          )}
        </div>
      </div>
    </div>
  );
});

ErrorMessage.displayName = 'ErrorMessage';

export { ErrorMessage };
