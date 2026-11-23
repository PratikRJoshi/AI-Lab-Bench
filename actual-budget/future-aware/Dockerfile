ARG ACTUAL_BASE_IMAGE=actualbudget/actual-server@sha256:06cf186569cf58d93e12659ff1a517b65b5b0ebee7050a3991d4bd8a1d398da6
FROM ${ACTUAL_BASE_IMAGE}
LABEL io.pratik.actual.future-aware="true"
COPY web/ /app/node_modules/@actual-app/web/build/
