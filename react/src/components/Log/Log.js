import { useState } from "react";
import { PaginationControl } from 'react-bootstrap-pagination-control';

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

    const logData = (log) => {
        console.log(log)
        return (
            <div>
                <div class="container text-start mb-3" data-testid="log">
                    {
                        if (log.length !=0) {
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
                                        <div class="col-12 log-message mb-1">{entry.message}</div>
                                        <hr class="dashed" />
                                    </div>
                                )
                            })
                        } else {
                            return (
                                <div class="row">
                                    ログがありません．
                                </dvi>
                            )
                        }
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