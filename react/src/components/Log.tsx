import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PaginationControl } from "react-bootstrap-pagination-control";
import { XCircleFill, ToggleOff, ToggleOn, Speedometer, SunriseFill, SunsetFill } from "react-bootstrap-icons";

import "dayjs/locale/ja";
import dayjs, { locale, extend } from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
locale("ja");
extend(relativeTime);

import { ApiResponse } from "../lib/ApiResponse";

type Props = {
    isReady: boolean;
    log: ApiResponse.Log;
};

const Log = React.memo(({ isReady, log }: Props) => {
    const [page, setPage] = useState(1);
    const size = 5;

    const handlePageChange = useCallback((page: number) => {
        setPage(page);
    }, []);

    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    const messageIcon = (message: string) => {
        if (message.match(/故障/)) {
            return (
                <span className="me-2 text-danger">
                    <XCircleFill />
                </span>
            );
        } else if (message.match(/開始/)) {
            return (
                <span className="me-2 text-danger">
                    <SunriseFill />
                </span>
            );
        } else if (message.match(/停止/)) {
            return (
                <span className="me-2 text-warning">
                    <SunsetFill />
                </span>
            );
        } else if (message.match(/ON Duty/)) {
            return (
                <span className="me-2 text-success">
                    <ToggleOn />
                </span>
            );
        } else if (message.match(/OFF Duty/)) {
            return (
                <span className="me-2 text-secondary">
                    <ToggleOff />
                </span>
            );
        } else if (message.match(/変更/)) {
            return (
                <span className="me-2 text-success">
                    <Speedometer />
                </span>
            );
        }
    };

    const formatMessage = (message: string) => {
        return (
            <span>
                {messageIcon(message)}
                {message}
            </span>
        );
    };

    const logData = (log: ApiResponse.LogEntry[]) => {
        if (log.length === 0) {
            return (
                <div>
                    <div className="container text-start mb-3" data-testid="log">
                        <div className="row">ログがありません．</div>
                    </div>
                </div>
            );
        }

        return (
            <div>
                <div className="container text-start mb-3" data-testid="log">
                    <AnimatePresence initial={false}>
                        {log.slice((page - 1) * size, page * size).map((entry: ApiResponse.LogEntry) => {
                            let date = dayjs(entry.date);
                            let log_date = date.format("M月D日(ddd) HH:mm");
                            let log_fromNow = date.fromNow();

                            return (
                                <motion.div
                                    className="row"
                                    key={entry.id}
                                    initial={{ opacity: 0, height: 0, y: -20 }}
                                    animate={{ opacity: 1, height: "auto", y: 0 }}
                                    exit={{ opacity: 0, height: 0, y: -20 }}
                                    transition={{
                                        duration: 0.3,
                                        ease: "easeOut"
                                    }}
                                    layout
                                >
                                    <div className="col-12 font-weight-bold">
                                        {log_date}
                                        <small className="text-muted">({log_fromNow})</small>
                                    </div>
                                    <div className="col-12 log-message mb-1">{formatMessage(entry.message)}</div>
                                    <hr className="dashed" />
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>
                </div>

                <div className="position-absolute bottom-0 start-50 translate-middle-x">
                    <PaginationControl
                        page={page}
                        between={3}
                        total={log.length}
                        limit={size}
                        changePage={handlePageChange}
                        ellipsis={1}
                    />
                </div>
            </div>
        );
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">作動ログ</h4>
                    </div>
                    <div className="card-body">{isReady ? logData(log.data) : loading()}</div>
                </div>
            </div>
        </div>
    );
});

Log.displayName = 'Log';

export { Log };
