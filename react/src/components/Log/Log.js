import { useState } from "react";
import { PaginationControl } from 'react-bootstrap-pagination-control';
import { ToggleOff, ToggleOn, Speedometer, SunriseFill, SunsetFill  } from 'react-bootstrap-icons';

import moment from "moment-timezone";
import "moment/locale/ja";

const Log = ({ isReady, log }) => {
    const [page, setPage] = useState(1)
    const size = 5

    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    const messageIcon  = (message) => {
        if (message.match(/開始/)) {
            return (
                <span class="me-2 text-success">
                    <SunriseFill />
                </span>
            )
        } else if (message.match(/停止/)) {
            return (
                <span class="me-2 text-warning">
                    <SunsetFill />
                </span>
            )
        } else if (message.match(/ON Duty/)) {
            return (
                <span class="me-2 text-success">
                    <ToggleOn />
                </span>
                    
            )
        } else if (message.match(/OFF Duty/)) {
            return (
                <span class="me-2 text-secondary">
                    <ToggleOff />
                </span>
            )
        } else if (message.match(/変更/)) {
            return (
                <span class="me-2 text-success">
                    <Speedometer />
                </span>
            )
        }
    }
    
    const formatMessage  = (message) => {
        return (
            <span>
                {messageIcon(message)}
                {message}
            </span>
        )
    };

    const logData = (log) => {
        if (log.length === 0) {
            return (
                <div>
                    <div class="container text-start mb-3" data-testid="log">
                        <div class="row">
                            ログがありません．
                        </div>
                    </div>
                </div>
            )
        }

        return (
            <div>
                <div class="container text-start mb-3" data-testid="log">
                    {
                        log.slice((page - 1) * size, page * size).map((entry, index) => {
                            let date = moment(entry.date)
                            let log_date = date.format("M月D日(ddd) HH:mm");
                            let log_fromNow = date.fromNow();
                                
                            return (
                                <div class="row">
                                        <div class="col-12 font-weight-bold">
                                            { log_date }
                                            <small class="text-muted">({ log_fromNow })</small>
                                        </div>
                                    <div class="col-12 log-message mb-1">{formatMessage(entry.message)}</div>
                                        <hr class="dashed" />
                                    </div>
                                )
                            })
                    }
                </div>

                <div class="position-absolute bottom-0 start-50 translate-middle-x">
                    <PaginationControl
                        page={page}
                        between={3}
                        total={log.length}
                        limit={size}
                        changePage={(page) => {
                            setPage(page); 
                        }}
                        ellipsis={1}
                    />
                </div>
            </div>
        )
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">ログ</h4>
                    </div>
                    <div className="card-body">{isReady ? logData(log) : loading()}</div>
                </div>
            </div>
        </div>
    );
};

export default Log;
